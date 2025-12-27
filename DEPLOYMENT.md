# Cloud Deployment Guide

This guide provides instructions for deploying the ETL Backend Service to various cloud providers.

## 🚀 Quick Start: Render Deployment (Automatic)

### Prerequisites
- Code pushed to GitHub
- Render account connected to GitHub repository

### Deployment Steps

1. **Push your changes:**
   ```bash
   git add .
   git commit -m "Add identity unification feature"
   git push origin main
   ```

2. **Automatic deployment happens:**
   - Render detects push and builds Docker image
   - Runs `docker-entrypoint.sh` which includes `migrate_db.py`
   - Service starts with new features enabled

3. **Verify deployment:**
   ```bash
   # Health check
   curl https://your-service.onrender.com/health
   
   # Check canonical_id in data
   curl https://your-service.onrender.com/api/data?limit=5
   ```

### Manual Migration (If Needed)

If automatic migration fails, run manually via Render Shell:

```bash
# In Render Dashboard → Shell
python run_migration_manual.py
```

### Post-Deployment Checklist

✅ Health endpoint returns `database_connected: true`  
✅ API responses include `canonical_id` field  
✅ No "canonical_id does not exist" errors in logs  
✅ ETL pipeline completes successfully  

---

## AWS Deployment

### Prerequisites
- AWS CLI configured
- Docker installed locally
- AWS account with appropriate permissions

### Option 1: AWS ECS (Elastic Container Service)

#### 1. Build and Push Docker Image

```bash
# Authenticate Docker to AWS ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repository
aws ecr create-repository --repository-name etl-backend-service

# Build and tag image
docker build -t etl-backend-service:latest .
docker tag etl-backend-service:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/etl-backend-service:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/etl-backend-service:latest
```

#### 2. Set Up RDS PostgreSQL

```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier etl-postgres \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username postgres \
  --master-user-password <secure-password> \
  --allocated-storage 20 \
  --vpc-security-group-ids <security-group-id>
```

#### 3. Store Secrets in AWS Secrets Manager

```bash
# Store API keys
aws secretsmanager create-secret \
  --name etl-api-keys \
  --secret-string '{
    "API_KEY_SOURCE_1": "your-api-key",
    "API_KEY_SOURCE_2": "your-api-key",
    "DB_PASSWORD": "your-db-password"
  }'
```

#### 4. Create ECS Task Definition

Create `ecs-task-definition.json`:

```json
{
  "family": "etl-backend-service",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "etl-service",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/etl-backend-service:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://postgres:password@rds-endpoint:5432/etl_db"
        },
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        }
      ],
      "secrets": [
        {
          "name": "API_KEY_SOURCE_1",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:etl-api-keys:API_KEY_SOURCE_1::"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/etl-backend-service",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### 5. Create ECS Service

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create ECS cluster
aws ecs create-cluster --cluster-name etl-cluster

# Create service
aws ecs create-service \
  --cluster etl-cluster \
  --service-name etl-service \
  --task-definition etl-backend-service \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

#### 6. Set Up Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name etl-alb \
  --subnets subnet-xxx subnet-yyy \
  --security-groups sg-xxx

# Create target group
aws elbv2 create-target-group \
  --name etl-targets \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --target-type ip \
  --health-check-path /health

# Create listener
aws elbv2 create-listener \
  --load-balancer-arn <alb-arn> \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=<target-group-arn>
```

#### 7. Schedule ETL Runs with EventBridge

```bash
# Create EventBridge rule (every 6 hours)
aws events put-rule \
  --name etl-schedule \
  --schedule-expression "rate(6 hours)"

# Add ECS task as target
aws events put-targets \
  --rule etl-schedule \
  --targets "Id"="1","Arn"="arn:aws:ecs:region:account:cluster/etl-cluster","RoleArn"="<ecs-events-role-arn>","EcsParameters"="{TaskDefinitionArn=<task-def-arn>,TaskCount=1,LaunchType=FARGATE}"
```

### Option 2: AWS EC2

#### 1. Launch EC2 Instance

```bash
# Create EC2 instance
aws ec2 run-instances \
  --image-id ami-xxx \
  --instance-type t3.medium \
  --key-name your-key \
  --security-group-ids sg-xxx \
  --subnet-id subnet-xxx \
  --user-data file://user-data.sh
```

#### 2. User Data Script (`user-data.sh`)

```bash
#!/bin/bash
yum update -y
yum install -y docker
service docker start
usermod -a -G docker ec2-user

# Install docker-compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Clone repository
cd /home/ec2-user
git clone <your-repo-url> etl-backend
cd etl-backend

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://postgres:password@rds-endpoint:5432/etl_db
API_KEY_SOURCE_1=your-key
# ... other variables
EOF

# Start services
docker-compose up -d

# Set up cron for ETL
echo "0 */6 * * * docker-compose exec -T etl_service python -m ingestion.etl_orchestrator" | crontab -
```

## Google Cloud Platform (GCP) Deployment

### Option 1: Google Cloud Run

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/etl-backend-service

# Deploy to Cloud Run
gcloud run deploy etl-backend-service \
  --image gcr.io/PROJECT_ID/etl-backend-service \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=postgresql://... \
  --set-secrets API_KEY_SOURCE_1=etl-api-keys:latest

# Set up Cloud Scheduler
gcloud scheduler jobs create http etl-trigger \
  --schedule "0 */6 * * *" \
  --uri "https://etl-backend-service-xxx.run.app/trigger-etl" \
  --http-method POST
```

### Option 2: Google Kubernetes Engine (GKE)

```bash
# Create GKE cluster
gcloud container clusters create etl-cluster \
  --num-nodes 2 \
  --machine-type n1-standard-2

# Deploy application
kubectl apply -f k8s-deployment.yaml
kubectl apply -f k8s-service.yaml
kubectl apply -f k8s-ingress.yaml
```

## Microsoft Azure Deployment

### Azure Container Instances

```bash
# Create resource group
az group create --name etl-rg --location eastus

# Create PostgreSQL
az postgres flexible-server create \
  --resource-group etl-rg \
  --name etl-postgres \
  --admin-user postgres \
  --admin-password <secure-password>

# Create container instance
az container create \
  --resource-group etl-rg \
  --name etl-backend-service \
  --image your-registry/etl-backend-service:latest \
  --cpu 1 \
  --memory 2 \
  --ports 8000 \
  --environment-variables \
    DATABASE_URL=postgresql://... \
    ENVIRONMENT=production \
  --secure-environment-variables \
    API_KEY_SOURCE_1=your-key

# Set up Logic Apps for scheduling
az logic workflow create \
  --resource-group etl-rg \
  --name etl-scheduler \
  --definition @logic-app-definition.json
```

## Monitoring & Logging

### CloudWatch (AWS)

```bash
# Create log group
aws logs create-log-group --log-group-name /ecs/etl-backend-service

# Create metric alarm
aws cloudwatch put-metric-alarm \
  --alarm-name etl-high-error-rate \
  --alarm-description "Alert when ETL error rate is high" \
  --metric-name Errors \
  --namespace AWS/ECS \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

### Application Insights (Azure)

```bash
# Create Application Insights
az monitor app-insights component create \
  --app etl-backend-insights \
  --location eastus \
  --resource-group etl-rg

# Get instrumentation key
az monitor app-insights component show \
  --app etl-backend-insights \
  --resource-group etl-rg \
  --query instrumentationKey
```

## Scaling Configuration

### Auto-scaling (AWS ECS)

```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/etl-cluster/etl-service \
  --min-capacity 1 \
  --max-capacity 5

# Create scaling policy
aws application-autoscaling put-scaling-policy \
  --policy-name cpu-scaling \
  --service-namespace ecs \
  --resource-id service/etl-cluster/etl-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

## Security Best Practices

1. **Use Secret Management**
   - AWS Secrets Manager / Parameter Store
   - GCP Secret Manager
   - Azure Key Vault

2. **Network Security**
   - Use VPC/VNet for isolation
   - Configure security groups/firewall rules
   - Use private subnets for database

3. **SSL/TLS**
   - Use HTTPS for all endpoints
   - Configure SSL certificates via ALB/Cloud Load Balancer

4. **IAM Roles**
   - Use minimal permission policies
   - Rotate credentials regularly
   - Enable MFA for administrative access

5. **Monitoring**
   - Enable CloudTrail/Cloud Audit Logs
   - Set up alerts for failures
   - Monitor costs and resource usage

## Cost Optimization

1. **Use Spot Instances** (AWS EC2)
2. **Right-size Resources** (monitor CPU/memory usage)
3. **Use Reserved Instances** for predictable workloads
4. **Implement Auto-scaling** to scale down during low usage
5. **Clean up Unused Resources** regularly

## Disaster Recovery

1. **Database Backups**
   ```bash
   # AWS RDS automated backups
   aws rds modify-db-instance \
     --db-instance-identifier etl-postgres \
     --backup-retention-period 7
   ```

2. **Multi-Region Deployment**
   - Deploy to multiple regions for high availability
   - Use cross-region replication for database

3. **Health Checks**
   - Configure health check endpoints
   - Set up automatic recovery on failure

## Troubleshooting

### Check Logs
```bash
# AWS CloudWatch
aws logs tail /ecs/etl-backend-service --follow

# GCP
gcloud logging read "resource.type=cloud_run_revision"

# Azure
az monitor app-insights query --app etl-backend-insights --analytics-query "traces | limit 100"
```

### Access Container Shell
```bash
# AWS ECS
aws ecs execute-command \
  --cluster etl-cluster \
  --task <task-id> \
  --container etl-service \
  --interactive \
  --command "/bin/bash"
```

---

For specific deployment questions, refer to the cloud provider documentation or contact the development team.
