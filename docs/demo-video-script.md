# Demo video script (3 minutes)

Record the deployed site (the CloudFront URL) in a 1440 px wide browser. Speak slowly. Each scene lists **what's on screen** and **what to say**. The times add up to about 3:00.

## 1. The problem (0:00–0:20)
**Screen:** the landing page with the 3D India terrain and the live numbers.
**Say:** "Every year, drought, floods and heat leave millions of Indians without water. The warnings are already out there, in news, on social media and in government orders. But they're scattered, in many languages, and nobody can act on them fast. We built one live picture of every water crisis in India."

## 2. The live map (0:20–0:50)
**Screen:** click "Open the map". Switch the hazard tabs (Drought → Flood → Heat → Water supply). Hover a zone.
**Say:** "Twice a day our pipeline reads news from GDELT and RSS, plus Reddit and X. It filters out old and duplicate posts, then an AI model on Amazon Bedrock reads each post and labels it: drought, flood, heat or a water-supply failure. Posts are placed on the map and grouped into zones. Each zone has a score, so officials see the worst places first."

## 3. Why drought is different: measured data (0:50–1:25)
**Screen:** Drought tab; zoom into Maharashtra (Solapur and Marathwada). Open one taluka zone and scroll to the drought panel.
**Say:** "News alone can't tell you where a drought is. One article once made a whole district look dry. So drought follows the Government of India Drought Manual. Each taluka is checked against satellite rainfall (CHIRPS SPI) and soil moisture from Copernicus. 'People affected' counts only the people who live in the dry grid cells, not the whole district. That's what makes tanker and budget numbers honest."

## 4. Official declarations, read automatically (1:25–2:00)
**Screen:** on the same zone page, the "Declared" badge and the order note. Then the ops page, "Declaration watch" box.
**Say:** "Governments declare drought in long PDFs, often in Marathi with broken fonts. We read Maharashtra's 265-taluka order automatically: 230 talukas matched, checked against the order's own counts per district, and the doubtful ones go to a person. For other states, a watcher reads declaration news every day. It loads a taluka only if an official order, or two independent news sites, name it. Demands and 'may be declared' are ignored."

## 5. Evidence you can trust (2:00–2:15)
**Screen:** zone page: the evidence quotes, the score breakdown, the trend.
**Say:** "Every zone shows its evidence. The quotes are word for word from the source, and the AI isn't allowed to invent numbers. Every number on this page is computed in code, and you can see the arithmetic."

## 5b. From zone to water on the ground (2:15–2:35)
**Screen:** on the zone page, the "Drinking water needed from tankers" card. Click "Create tanker tender" and publish (the demo code is already entered). On the tender page, switch "Viewing as" to the top vendor, click Counter (₹64), switch back to the government and click Accept. The committed bar fills.
**Say:** "From a zone, the officer sees how much drinking water the rural families need: the formula is right there. One click publishes a tender. The nearest reliable tanker vendors are invited, each with a plain reason. Vendors can accept or counter, and the bar shows how much water is already committed."

## 6. Built on AWS (2:35–2:55)
**Screen:** an architecture slide (or the AWS console: the CloudFormation stack, the ECS service, RDS).
**Say:** "It all runs on AWS in Mumbai, built as code with the AWS CDK. The website is on S3 and CloudFront. The API runs on ECS Fargate behind a load balancer. The data lives in RDS PostgreSQL with PostGIS for the maps. EventBridge runs the pipeline on a schedule. Secrets Manager holds the keys, Amazon Bedrock reads the posts, Amazon Location finds places, and S3 archives every raw post."

## 7. Close (2:55–3:00)
**Screen:** back to the map.
**Say:** "One live, honest picture of India's water crises, so relief reaches the right taluka first."

## Recording tips
- Close other tabs and turn off notifications. Zoom the browser to 110% so text is readable.
- Keep the mouse still while talking; move it only to click.
- If something loads slowly, cut that part in editing.
