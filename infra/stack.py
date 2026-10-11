"""Everything the platform needs on AWS, in one stack.

Network has no NAT gateway (saves ~$35/month): the API / pipeline tasks run in public subnets with a public IP so they
can reach GDELT, Groq and Apify; the database sits in isolated subnets that only the tasks can reach; the load balancer
only accepts CloudFront.
"""
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk.aws_ecr_assets import Platform
from constructs import Construct

from config import APP_SECRET_NAME, PIPELINE_CRON_HOURS, PROJECT

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = "web"

# single-page app: any path without a file extension is a client-side route -> index.html
SPA_REWRITE = """
function handler(event) {
  var request = event.request;
  if (!request.uri.includes('.')) { request.uri = '/index.html'; }
  return request;
}
"""


class PlatformStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=0, subnet_configuration=[
            ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
            ec2.SubnetConfiguration(name="data", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24),
        ])

        # -- database ------------------------------------------------------------------------------------------
        db = rds.DatabaseInstance(
            self, "Db",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.of("16.15", "16")),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MICRO),
            vpc=vpc, vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            credentials=rds.Credentials.from_generated_secret("jaladmin", secret_name=f"{PROJECT}/db"),
            database_name="jal", allocated_storage=20, storage_type=rds.StorageType.GP3, multi_az=False,
            backup_retention=cdk.Duration.days(1), deletion_protection=False,
            removal_policy=cdk.RemovalPolicy.SNAPSHOT, publicly_accessible=False, storage_encrypted=True,
        )

        # -- storage -------------------------------------------------------------------------------------------
        raw = s3.Bucket(self, "Raw", block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True,
                        encryption=s3.BucketEncryption.S3_MANAGED)  # raw post archive + database dumps
        site = s3.Bucket(self, "Site", block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True,
                         removal_policy=cdk.RemovalPolicy.DESTROY, auto_delete_objects=True)

        # -- API on Fargate behind a load balancer --------------------------------------------------------------
        app_secret = secretsmanager.Secret.from_secret_name_v2(self, "AppSecret", APP_SECRET_NAME)
        image = ecs.ContainerImage.from_asset(str(ROOT / "backend"), platform=Platform.LINUX_AMD64)
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, container_insights_v2=ecs.ContainerInsights.DISABLED)
        secrets = {
            "DB_HOST": ecs.Secret.from_secrets_manager(db.secret, "host"),
            "DB_PORT": ecs.Secret.from_secrets_manager(db.secret, "port"),
            "DB_USER": ecs.Secret.from_secrets_manager(db.secret, "username"),
            "DB_PASSWORD": ecs.Secret.from_secrets_manager(db.secret, "password"),
            "GROQ_API_KEY": ecs.Secret.from_secrets_manager(app_secret, "GROQ_API_KEY"),
            "APIFY_TOKEN": ecs.Secret.from_secrets_manager(app_secret, "APIFY_TOKEN"),
            "ADMIN_TOKEN": ecs.Secret.from_secrets_manager(app_secret, "ADMIN_TOKEN"),
        }
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "Api", cluster=cluster, cpu=1024, memory_limit_mib=2048, desired_count=1, min_healthy_percent=100,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC), assign_public_ip=True,
            public_load_balancer=True, open_listener=False, circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            health_check_grace_period=cdk.Duration.seconds(120),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=image, container_name=CONTAINER, container_port=8000,
                environment={"DB_NAME": "jal", "RAW_BUCKET": raw.bucket_name, "AWS_REGION": self.region},
                secrets=secrets,
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="api", log_retention=logs.RetentionDays.TWO_WEEKS),
            ),
        )
        service.target_group.configure_health_check(path="/health", healthy_http_codes="200")
        service.load_balancer.set_attribute("idle_timeout.timeout_seconds", "3600")  # live feed (SSE) stays open
        cloudfront_only = ec2.PrefixList.from_lookup(self, "CloudFrontPrefixList",
                                                     prefix_list_name="com.amazonaws.global.cloudfront.origin-facing")
        service.load_balancer.connections.allow_from(ec2.Peer.prefix_list(cloudfront_only.prefix_list_id),
                                                     ec2.Port.tcp(80), "CloudFront only")
        db.connections.allow_default_port_from(service.service, "API and pipeline tasks")

        role = service.task_definition.task_role
        raw.grant_read_write(role)
        role.add_to_principal_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:Converse"],
            resources=["*"]))  # Nova Lite / Claude through cross-region inference profiles
        role.add_to_principal_policy(iam.PolicyStatement(actions=["geo-places:Geocode"], resources=["*"]))

        # -- pipeline twice a day: the same task, a different command ------------------------------------------
        rule = events.Rule(self, "PipelineSchedule",
                           schedule=events.Schedule.cron(minute="0", hour=PIPELINE_CRON_HOURS))
        rule.add_target(targets.EcsTask(
            cluster=cluster, task_definition=service.task_definition,
            subnet_selection=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC), assign_public_ip=True,
            security_groups=list(service.service.connections.security_groups),
            container_overrides=[targets.ContainerOverride(container_name=CONTAINER,
                                                           command=["python", "-m", "app.cli.run_pipeline"])],
        ))

        # -- website: S3 behind CloudFront, /api/* to the load balancer -----------------------------------------
        spa = cloudfront.Function(self, "SpaRewrite", code=cloudfront.FunctionCode.from_inline(SPA_REWRITE),
                                  runtime=cloudfront.FunctionRuntime.JS_2_0)
        distribution = cloudfront.Distribution(
            self, "Web",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(site),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                function_associations=[cloudfront.FunctionAssociation(
                    function=spa, event_type=cloudfront.FunctionEventType.VIEWER_REQUEST)]),
            additional_behaviors={"/api/*": cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(service.load_balancer,
                                                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                                                    read_timeout=cdk.Duration.seconds(60)),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER)},
            price_class=cloudfront.PriceClass.PRICE_CLASS_200,  # includes India edge locations
        )
        s3deploy.BucketDeployment(self, "SiteFiles", sources=[s3deploy.Source.asset(str(ROOT / "frontend" / "dist"))],
                                  destination_bucket=site, distribution=distribution, distribution_paths=["/*"],
                                  memory_limit=512)

        cdk.CfnOutput(self, "WebsiteUrl", value=f"https://{distribution.distribution_domain_name}")
        cdk.CfnOutput(self, "RawBucket", value=raw.bucket_name)
        cdk.CfnOutput(self, "ClusterName", value=cluster.cluster_name)
        cdk.CfnOutput(self, "TaskDefinition", value=service.task_definition.task_definition_arn)
        cdk.CfnOutput(self, "PublicSubnets", value=",".join(s.subnet_id for s in vpc.public_subnets))
        cdk.CfnOutput(self, "TaskSecurityGroup",
                      value=service.service.connections.security_groups[0].security_group_id)
