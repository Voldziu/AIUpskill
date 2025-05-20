
param location string = resourceGroup().location


param keyVaultName string = 'kv-${uniqueString(resourceGroup().id)}'


param tenantId string = subscription().tenantId


param objectId string

// Create the Key Vault resource
resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: keyVaultName
  location: location
  properties: {
    tenantId: tenantId
    sku: {
      name: 'standard'
      family: 'A'
    }
    accessPolicies: [
      {
        tenantId: tenantId
        objectId: objectId
        permissions: {
          secrets: [
            'get'
            'list'
            'set'
            'delete'
          ]
        }
      }
    ]
  }
}


output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
