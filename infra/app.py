"""CDK app: one stack with everything. Deploy: `npx cdk deploy --profile spice`; remove: `npx cdk destroy --profile spice`."""
import aws_cdk as cdk

from config import ACCOUNT, PROJECT, REGION
from stack import PlatformStack

app = cdk.App()
PlatformStack(app, f"{PROJECT}-platform", env=cdk.Environment(account=ACCOUNT, region=REGION),
              description="India water-crisis intelligence platform: website, API, database, scheduled pipeline")
app.synth()
