# PowerShell Azure Deployment Script for OmniDoc AI Platform
param (
    [string]$ResourceGroupName = "rg-omnidoc-ai",
    [string]$Location = "eastus"
)

$ErrorActionPreference = "Stop"

Write-Host "=== 1. Checking Azure CLI Login Status ===" -ForegroundColor Cyan
$azContext = az account show 2>$null
if (-not $azContext) {
    Write-Host "Not logged in to Azure. Launching 'az login'..." -ForegroundColor Yellow
    az login
}

Write-Host "=== 2. Creating Resource Group '$ResourceGroupName' in '$Location' ===" -ForegroundColor Cyan
az group create --name $ResourceGroupName --location $Location

Write-Host "=== 3. Deploying Bicep Infrastructure (Container Apps, Azure Doc Intel, Storage) ===" -ForegroundColor Cyan
$deployOutput = az deployment group create `
    --resource-group $ResourceGroupName `
    --template-file "./infrastructure/main.bicep" `
    --output json | ConvertFrom-Json

$publicUrl = $deployOutput.properties.outputs.publicAppUrl.value
$docIntelEndpoint = $deployOutput.properties.outputs.docIntelEndpoint.value

Write-Host "=== 4. Deploying Source Code to Azure Container App ===" -ForegroundColor Cyan
az containerapp up `
    --name "omnidoc-app" `
    --resource-group $ResourceGroupName `
    --source "." `
    --ingress external `
    --target-port 8000 `
    --env-vars MAX_CONCURRENT_USERS=10 DEMO_MODE=true AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=$docIntelEndpoint

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "SUCCESS! Your Multimodal AI Document Platform is LIVE!" -ForegroundColor Green
Write-Host "Shareable Public URL: $publicUrl" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Green
