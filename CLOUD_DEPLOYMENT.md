# Cloud Deployment Guide

This guide covers deploying the Kasparro ETL System to AWS, GCP, or Azure.

---

## Prerequisites

- Docker image built and tested locally
- Cloud provider account (AWS/GCP/Azure)
- Cloud CLI tools installed
- Domain name (optional, for public endpoints)

---

## Option 1: AWS Deployment

### 1. Push Docker Image to ECR

```bash
# Authenticate to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repository
aws ecr create-repository --repository-name kasparro-etl

# Tag and push image
docker tag kasparro-backend-saandeep-sijo-etl_service:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/kasparro-etl:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/kasparro-etl:latest
```

### 2. Deploy with ECS Fargate

Create `ecs-task-definition.json`:

```json
{
  "family": "kasparro-etl",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "etl-service",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/kasparro-etl:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "DATABASE_URL", "value": "postgresql://user:pass@rds-endpoint/etl_db"},
        {"name": "API_KEY_SOURCE_1", "value": "your-api-key"},
        {"name": "ENVIRONMENT", "value": "production"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/kasparro-etl",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

Deploy:

```bash
# Create log group
aws logs create-log-group --log-group-name /ecs/kasparro-etl

# Register task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create ECS cluster
aws ecs create-cluster --cluster-name kasparro-cluster

# Create service with ALB
aws ecs create-service \
  --cluster kasparro-cluster \
  --service-name kasparro-etl-service \
  --task-definition kasparro-etl \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### 3. Set Up RDS PostgreSQL

```bash
# Create RDS PostgreSQL instance
aws rds create-db-instance \
  --db-instance-identifier kasparro-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.3 \
  --master-username postgres \
  --master-user-password <secure-password> \
  --allocated-storage 20 \
  --publicly-accessible
```

### 4. Configure EventBridge for Cron

Create `eventbridge-rule.json`:

```json
{
  "Name": "kasparro-etl-schedule",
  "ScheduleExpression": "cron(0 */6 * * ? *)",
  "State": "ENABLED",
  "Targets": [
    {
      "Arn": "arn:aws:ecs:us-east-1:<account-id>:cluster/kasparro-cluster",
      "RoleArn": "arn:aws:iam::<account-id>:role/ecsEventsRole",
      "EcsParameters": {
        "TaskDefinitionArn": "arn:aws:ecs:us-east-1:<account-id>:task-definition/kasparro-etl:1",
        "TaskCount": 1,
        "LaunchType": "FARGATE",
        "NetworkConfiguration": {
          "awsvpcConfiguration": {
            "Subnets": ["subnet-xxx"],
            "SecurityGroups": ["sg-xxx"],
            "AssignPublicIp": "ENABLED"
          }
        }
      }
    }
  ]
}
```

Deploy:

```bash
# Create EventBridge rule
aws events put-rule --name kasparro-etl-schedule --schedule-expression "cron(0 */6 * * ? *)"

# Add ECS task as target
aws events put-targets --rule kasparro-etl-schedule --cli-input-json file://eventbridge-targets.json
```

### 5. Access Logs and Metrics

```bash
# View logs
aws logs tail /ecs/kasparro-etl --follow

# View CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=kasparro-etl-service \
  --start-time 2025-12-25T00:00:00Z \
  --end-time 2025-12-25T23:59:59Z \
  --period 3600 \
  --statistics Average
```

**Public Endpoint:** 
- Access via ALB DNS: `http://kasparro-alb-xxx.us-east-1.elb.amazonaws.com:8000`
- Or configure Route53 for custom domain

---

## Option 2: GCP Deployment

### 1. Push to Google Container Registry

```bash
# Configure Docker for GCR
gcloud auth configure-docker

# Tag and push
docker tag kasparro-backend-saandeep-sijo-etl_service:latest gcr.io/<project-id>/kasparro-etl:latest
docker push gcr.io/<project-id>/kasparro-etl:latest
```

### 2. Deploy to Cloud Run

```bash
# Create Cloud SQL PostgreSQL instance
gcloud sql instances create kasparro-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# Deploy to Cloud Run
gcloud run deploy kasparro-etl \
  --image gcr.io/<project-id>/kasparro-etl:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000 \
  --set-env-vars DATABASE_URL="postgresql://...",API_KEY_SOURCE_1="..." \
  --add-cloudsql-instances <project-id>:us-central1:kasparro-db \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 5
```

### 3. Configure Cloud Scheduler

```bash
# Create cron job
gcloud scheduler jobs create http kasparro-etl-schedule \
  --schedule "0 */6 * * *" \
  --uri "https://kasparro-etl-xxx.run.app/trigger-etl" \
  --http-method POST \
  --location us-central1
```

### 4. View Logs

```bash
# Stream logs
gcloud run services logs read kasparro-etl --follow --limit 100
```

**Public Endpoint:** `https://kasparro-etl-xxx.run.app`

---

## Option 3: Azure Deployment

### 1. Push to Azure Container Registry

```bash
# Login to Azure
az login

# Create ACR
az acr create --resource-group kasparro-rg --name kasparroregistry --sku Basic

# Login to ACR
az acr login --name kasparroregistry

# Tag and push
docker tag kasparro-backend-saandeep-sijo-etl_service:latest kasparroregistry.azurecr.io/kasparro-etl:latest
docker push kasparroregistry.azurecr.io/kasparro-etl:latest
```

### 2. Deploy to Azure Container Instances

```bash
# Create PostgreSQL
az postgres flexible-server create \
  --resource-group kasparro-rg \
  --name kasparro-db \
  --location eastus \
  --admin-user postgres \
  --admin-password <secure-password> \
  --sku-name Standard_B1ms \
  --version 15

# Deploy container
az container create \
  --resource-group kasparro-rg \
  --name kasparro-etl \
  --image kasparroregistry.azurecr.io/kasparro-etl:latest \
  --registry-login-server kasparroregistry.azurecr.io \
  --registry-username <username> \
  --registry-password <password> \
  --dns-name-label kasparro-etl \
  --ports 8000 \
  --environment-variables \
    DATABASE_URL="postgresql://..." \
    API_KEY_SOURCE_1="..." \
  --cpu 1 \
  --memory 1
```

### 3. Configure Azure Logic Apps for Cron

Create Logic App with:
- Trigger: Recurrence (every 6 hours)
- Action: HTTP POST to `http://kasparro-etl.eastus.azurecontainer.io:8000/trigger-etl`

### 4. View Logs

```bash
# View container logs
az container logs --resource-group kasparro-rg --name kasparro-etl --follow
```

**Public Endpoint:** `http://kasparro-etl.eastus.azurecontainer.io:8000`

---

## Environment Variables (All Platforms)

Ensure these are set in your cloud deployment:

```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname
API_KEY_SOURCE_1=<your-coinpaprika-api-key>
API_KEY_SOURCE_2=<your-coingecko-api-key>
API_URL_SOURCE_1=https://api.coinpaprika.com/v1/tickers
API_URL_SOURCE_2=https://api.coingecko.com/api/v3/coins/markets
RSS_FEED_URL=https://cointelegraph.com/rss
CSV_SOURCE_PATH=/app/data/sample_data.csv
ENVIRONMENT=production
LOG_LEVEL=INFO
ETL_RATE_LIMIT_CALLS=100
ETL_RATE_LIMIT_PERIOD=60
```

---

## Security Best Practices

1. **Never commit API keys** - Use cloud secret managers:
   - AWS: Secrets Manager
   - GCP: Secret Manager
   - Azure: Key Vault

2. **Use IAM roles** instead of hardcoded credentials

3. **Enable HTTPS** for public endpoints (use ALB/Cloud Run/Azure Front Door)

4. **Restrict database access** to VPC/private network

5. **Enable audit logging** in cloud console

---

## Monitoring & Alerts

### CloudWatch (AWS)
- Dashboard: `https://console.aws.amazon.com/cloudwatch/home`
- Metrics: CPU, Memory, Request Count
- Alarms: Set thresholds for failures

### Cloud Monitoring (GCP)
- Dashboard: `https://console.cloud.google.com/monitoring`
- Logs Explorer: Query structured JSON logs
- Uptime checks: Monitor endpoint availability

### Azure Monitor
- Dashboard: `https://portal.azure.com/#blade/Microsoft_Azure_Monitoring`
- Application Insights: Request tracking
- Log Analytics: Query logs with KQL

---

## Verification Checklist for Evaluators

✅ **Docker Image**
- Run locally: `docker-compose up -d`
- Health check: `curl http://localhost:8000/health`

✅ **Cloud Deployment**
- Public URL accessible: `curl https://your-cloud-url.com/health`
- Returns 200 OK with JSON response

✅ **Cron Jobs**
- EventBridge/Cloud Scheduler/Logic Apps configured
- Check "Last Execution" timestamp in cloud console
- Verify logs show scheduled runs

✅ **Logs & Metrics**
- CloudWatch/Cloud Logging/Azure Monitor shows logs
- Structured JSON format visible
- Prometheus metrics at `/observability/metrics`

✅ **ETL Resume**
- Stop container mid-run
- Restart container
- Verify checkpoints resume correctly (no duplicates)

✅ **API Correctness**
- `/data` returns paginated results
- `/stats` shows ETL statistics
- Filtering works: `/data?source_type=csv`

✅ **Rate Limiting**
- Check `/observability/metrics/json` for rate limit stats
- Verify retry logic in logs (3 attempts with backoff)

---

## Quick Deploy Script

Save as `deploy.sh`:

```bash
#!/bin/bash

# Quick deployment to AWS ECS
# Usage: ./deploy.sh <aws-account-id> <region>

ACCOUNT_ID=$1
REGION=${2:-us-east-1}
IMAGE_NAME="kasparro-etl"

echo "🚀 Deploying to AWS ECS..."

# Build and push
docker build -t $IMAGE_NAME .
docker tag $IMAGE_NAME:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$IMAGE_NAME:latest
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$IMAGE_NAME:latest

# Update service
aws ecs update-service --cluster kasparro-cluster --service kasparro-etl-service --force-new-deployment --region $REGION

echo "✅ Deployment complete!"
echo "📊 View logs: aws logs tail /ecs/kasparro-etl --follow"
```

Make executable: `chmod +x deploy.sh`

---

## Troubleshooting

**Issue:** Container fails health check
- Check logs: `docker-compose logs etl_service`
- Verify database connection
- Check environment variables

**Issue:** Cron not executing
- Verify IAM roles have ECS task execution permissions
- Check EventBridge/Scheduler is enabled
- View rule execution history in console

**Issue:** API returns 500 errors
- Check application logs
- Verify database migrations ran
- Test database connectivity

**Issue:** Rate limit not working
- Check environment variables: `ETL_RATE_LIMIT_CALLS`, `ETL_RATE_LIMIT_PERIOD`
- View metrics: `/observability/metrics/json`
- Check retry logs show backoff behavior
