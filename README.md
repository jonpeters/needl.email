# needl.email

## 🔧 Setup

1. **Create a SES Rule Set & Rule**

   - Go to **SES → Mail Manager → Rule Sets**
   - Create a rule set and add a rule to write email to S3

2. **Create a Traffic Policy**

   - Go to **Mail Manager → Traffic Policies**
   - Attach your rule set to a new or existing traffic policy

3. **Create an Ingress Endpoint**

   - Go to **Mail Manager → Ingress Endpoints**
   - Create a new endpoint using protocol `SMTP` and attach your traffic policy
   - Copy the generated **SMTP A record**

4. **Update Route 53 MX Record**

   - Go to **Route 53 → Hosted Zones → yourdomain.com**
   - Create an `MX` record pointing to your ingress endpoint’s A record:
     ```
     10 your-ingress-endpoint.mail-manager-smtp.amazonaws.com.
     ```

5. **Send a Test Email**
   - Email your domain (e.g. `test@yourdomain.com`)
   - Confirm the email lands in S3 and/or triggers your SQS queue
