@description('Azure AI Search service name')
param searchServiceName string = 'aisearchbrochures'

@description('Location for resources')
param location string = resourceGroup().location

@description('Search service SKU')
@allowed(['free', 'basic', 'standard', 'standard2', 'standard3'])
param sku string = 'basic'

// Storage account already exists from backup script

// Azure AI Search service
resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchServiceName
  location: location
  sku: {
    name: sku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
  }
}

// Output connection details
output searchServiceName string = searchService.name
output searchServiceEndpoint string = 'https://${searchService.name}.search.windows.net'