# PowerShell Enterprise FDE Azure Deployment Script for OmniDoc AI Platform
param (
    [string]$ResourceGroupName = "rg-explore-ai",
    [string]$Location = "eastus",
    [string]$AcrName = "acrexploreai65064",
    [string]$ImageTag = "v2-fde-latest"
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " OmniDoc AI - Enterprise Forward Deployed Engineering (FDE) Deploy" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Verify Azure CLI Authentication
Write-Host "`n[Step 1/5] Checking Azure CLI Session..." -ForegroundColor Yellow
$azContext = az account show 2>$null
if (-not $azContext) {
    Write-Host "Not authenticated with Azure. Launching 'az login'..." -ForegroundColor Yellow
    az login
}
$currentSub = (az account show --query "name" -o tsv)
Write-Host "Active Subscription: $currentSub" -ForegroundColor Green

# 2. ACR Build and Image Publishing
Write-Host "`n[Step 2/5] Building Docker Image via Azure Container Registry '$AcrName'..." -ForegroundColor Yellow
az acr build `
    --registry $AcrName `
    --image "omnidoc-fde-platform:$ImageTag" `
    --file "./Dockerfile" `
    "."

# 3. Retrieve Credentials from Active Azure Resources
Write-Host "`n[Step 3/5] Resolving Connection Strings & Credentials in '$ResourceGroupName'..." -ForegroundColor Yellow
$sbConn = az servicebus namespace authorization-rule keys list `
    --resource-group $ResourceGroupName `
    --namespace-name "sb-explore-ai" `
    --name "RootManageSharedAccessKey" `
    --query "primaryConnectionString" -o tsv

$stgConn = az storage account show-connection-string `
    --resource-group $ResourceGroupName `
    --name "stexploreai65064" `
    --query "connectionString" -o tsv

$docIntelKey = az cognitiveservices account keys list `
    --resource-group $ResourceGroupName `
    --name "omnidoc-docintel-k62z7k46ybsbm" `
    --query "key1" -o tsv

$docIntelEndpoint = az cognitiveservices account show `
    --resource-group $ResourceGroupName `
    --name "omnidoc-docintel-k62z7k46ybsbm" `
    --query "properties.endpoint" -o tsv

$appInsightsConn = az monitor app-insights component show `
    --resource-group $ResourceGroupName `
    --app "func-ai-microservice-65064" `
    --query "connectionString" -o tsv

# 4. Deploy / Update Azure Container App
Write-Host "`n[Step 4/5] Deploying Container to Azure Container App..." -ForegroundColor Yellow
$loginServer = az acr show --name $AcrName --query "loginServer" -o tsv
$fullImage = "$loginServer/omnidoc-fde-platform:$ImageTag"

az containerapp up `
    --name "omnidoc-fde-app" `
    --resource-group $ResourceGroupName `
    --environment "cae-explore-ai" `
    --image $fullImage `
    --ingress external `
    --target-port 8000 `
    --env-vars `
        AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=$docIntelEndpoint `
        AZURE_DOCUMENT_INTELLIGENCE_KEY=$docIntelKey `
        AZURE_STORAGE_CONNECTION_STRING=$stgConn `
        AZURE_STORAGE_CONTAINER_NAME="raw-documents" `
        AZURE_SERVICE_BUS_CONNECTION_STRING=$sbConn `
        AZURE_SERVICE_BUS_QUEUE_NAME="ai-jobs-queue" `
        AZURE_SERVICE_BUS_RESULTS_QUEUE="ai-results-queue" `
        APPLICATIONINSIGHTS_CONNECTION_STRING=$appInsightsConn `
        OTEL_SERVICE_NAME="omnidoc-fde-platform" `
        ENABLE_ASYNC_WORKER="true" `
        DEMO_MODE="false"

# 5. Verification & Health Check
Write-Host "`n[Step 5/5] Querying Live Application FQDN..." -ForegroundColor Yellow
$appFqdn = az containerapp show `
    --name "omnidoc-fde-app" `
    --resource-group $ResourceGroupName `
    --query "properties.configuration.ingress.fqdn" -o tsv

$liveUrl = "https://$appFqdn"
Write-Host "`n=================================================================" -ForegroundColor Green
Write-Host " SUCCESS! Enterprise FDE Platform is LIVE on Azure!" -ForegroundColor Green
Write-Host " Ingress URL: $liveUrl" -ForegroundColor Yellow
Write-Host " Health Check: $liveUrl/api/v1/health" -ForegroundColor Cyan
Write-Host " Swagger Docs: $liveUrl/docs" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Green
