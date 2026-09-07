// Azure Bicep Infrastructure Provisioning Template for OmniDoc AI Enterprise FDE Platform
@description('Location for all resources.')
param location string = resourceGroup().location

@description('Prefix for resource names.')
param appName string = 'omnidoc'

@description('Existing Container App Environment Name')
param existingEnvName string = 'cae-explore-ai'

@description('Existing Service Bus Namespace')
param existingServiceBusNamespace string = 'sb-explore-ai'

@description('Existing Storage Account Name')
param existingStorageAccountName string = 'stexploreai65064'

@description('Existing Document Intelligence Resource Name')
param existingDocIntelName string = 'omnidoc-docintel-k62z7k46ybsbm'

@description('Application Insights Connection String')
param appInsightsConnectionString string = 'InstrumentationKey=226bbf53-d96c-4230-84dc-88f6d9e71409;IngestionEndpoint=https://eastus-8.in.applicationinsights.azure.com/;LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/;ApplicationId=1800608f-a9e9-4d96-ae9c-fb34f4b7aeec'

var uniqueSuffix = uniqueString(resourceGroup().id)
var containerAppName = '${appName}-platform-${uniqueSuffix}'

// 1. Reference Existing Container Apps Managed Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: existingEnvName
}

// 2. Reference Existing Document Intelligence Resource
resource docIntelligence 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: existingDocIntelName
}

// 3. Reference Existing Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: existingStorageAccountName
}

// 4. Reference Existing Service Bus Namespace
resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' existing = {
  name: existingServiceBusNamespace
}

// 5. Azure Container App (FastAPI Enterprise Gateway & Background Worker with KEDA)
resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        allowInsecure: false
        transport: 'auto'
      }
      secrets: [
        {
          name: 'docintel-key'
          value: docIntelligence.listKeys().key1
        }
        {
          name: 'storage-key'
          value: storageAccount.listKeys().keys[0].value
        }
        {
          name: 'sb-connection'
          value: listKeys('${serviceBusNamespace.id}/AuthorizationRules/RootManageSharedAccessKey', '2022-10-01-preview').primaryConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'omnidoc-fde-engine'
          image: 'mcr.microsoft.com/azuredocs/aci-helloworld:latest'
          resources: {
            cpu: json('1.0')
            memory: '2.0Gi'
          }
          env: [
            {
              name: 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'
              value: docIntelligence.properties.endpoint
            }
            {
              name: 'AZURE_DOCUMENT_INTELLIGENCE_KEY'
              secretRef: 'docintel-key'
            }
            {
              name: 'AZURE_STORAGE_CONTAINER_NAME'
              value: 'raw-documents'
            }
            {
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
            }
            {
              name: 'AZURE_SERVICE_BUS_CONNECTION_STRING'
              secretRef: 'sb-connection'
            }
            {
              name: 'AZURE_SERVICE_BUS_QUEUE_NAME'
              value: 'ai-jobs-queue'
            }
            {
              name: 'AZURE_SERVICE_BUS_RESULTS_QUEUE'
              value: 'ai-results-queue'
            }
            {
              name: 'ENABLE_ASYNC_WORKER'
              value: 'true'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
            {
              name: 'OTEL_SERVICE_NAME'
              value: 'omnidoc-fde-platform'
            }
            {
              name: 'MAX_CONCURRENT_USERS'
              value: '20'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
        rules: [
          {
            name: 'http-scaling-rule'
            custom: {
              type: 'http'
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
          {
            name: 'keda-servicebus-queue-rule'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                queueName: 'ai-jobs-queue'
                messageCount: '5'
              }
              auth: [
                {
                  secretRef: 'sb-connection'
                  triggerParameter: 'connection'
                }
              ]
            }
          }
        ]
      }
    }
  }
}

output publicAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output containerAppName string = containerApp.name
output docIntelEndpoint string = docIntelligence.properties.endpoint
output storageAccountName string = storageAccount.name
output serviceBusNamespaceName string = serviceBusNamespace.name
