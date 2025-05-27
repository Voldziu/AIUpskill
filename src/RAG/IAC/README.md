# Azure AI Search Cost Management

Automated scripts to backup, delete, and restore Azure AI Search to avoid billing when not in use.

## Prerequisites

```powershell
Install-Module -Name Az.Search -Force
Install-Module -Name Az.Storage -Force  
Install-Module -Name Az.Resources -Force
Connect-AzAccount
```

## Usage Steps

### 1. Backup Existing Indexes
```powershell
.\backup_indexes.ps1
```
- Creates storage account if needed
- Saves all index schemas to blob storage
- **Note:** Only saves structure, not data

### 2. Delete Search Service (Stops Billing)
```powershell
.\delete_search_service.ps1
```
- Removes Azure AI Search service
- Index schemas remain in storage

### 3. Recreate When Needed
```powershell
.\create_search_service.ps1
```
- Deploys new search service using `deploy.bicep`
- Outputs API key for .env file

### 4. Restore Index Structure
```powershell
.\restore_indexes.ps1
```
- Recreates indexes from backup
- Indexes will be empty (structure only)

### 5. Re-Index PDF Data
- "Need to re-index PDF data in Azure AI Foundry. It will create new index with new name. Use that name."
## Files

- `deploy.bicep` - Search service template
- `backup_indexes.ps1` - Backup index schemas
- `delete_search_service.ps1` - Delete service
- `create_search_service.ps1` - Create service + show API key
- `restore_indexes.ps1` - Restore index structure
- `index-pdfs.ps1` - Re-upload PDF data

## Cost Savings

Only pay for Azure AI Search when actively using it. Storage costs are minimal (~$0.02/month).