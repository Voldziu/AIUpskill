# backup-indexes.ps1 - Backup indexes before deletion
param(
    [string]$ResourceGroupName = "rg-RAG",
    [string]$SearchServiceName = "aisearchbrochures",
    [string]$StorageAccountName = "searchindexbackup123"
)

# Create storage account if it doesn't exist
try {
    Get-AzStorageAccount -ResourceGroupName $ResourceGroupName -Name $StorageAccountName -ErrorAction Stop
    Write-Host "Storage account $StorageAccountName already exists"
}
catch {
    Write-Host "Creating storage account: $StorageAccountName"
    New-AzStorageAccount -ResourceGroupName $ResourceGroupName -Name $StorageAccountName -Location "Central US" -SkuName "Standard_LRS" -Kind "StorageV2"
}

# Get search service admin key
$adminKey = (Get-AzSearchAdminKeyPair -ResourceGroupName $ResourceGroupName -ServiceName $SearchServiceName).Primary

# Get storage account key and create context
$storageKey = (Get-AzStorageAccountKey -ResourceGroupName $ResourceGroupName -Name $StorageAccountName)[0].Value
$ctx = New-AzStorageContext -StorageAccountName $StorageAccountName -StorageAccountKey $storageKey

# Create container if it doesn't exist
try {
    Get-AzStorageContainer -Context $ctx -Name "index-definitions" -ErrorAction Stop
}
catch {
    Write-Host "Creating container: index-definitions"
    New-AzStorageContainer -Context $ctx -Name "index-definitions" -Permission Off
}

# Backup all indexes
$headers = @{
    'api-key' = $adminKey
    'Content-Type' = 'application/json'
}

$searchEndpoint = "https://$SearchServiceName.search.windows.net"
$indexes = Invoke-RestMethod -Uri "$searchEndpoint/indexes?api-version=2023-11-01" -Headers $headers

foreach ($index in $indexes.value) {
    Write-Host "Backing up index: $($index.name)"

    # Get full index definition
    $indexDef = Invoke-RestMethod -Uri "$searchEndpoint/indexes/$($index.name)?api-version=2023-11-01" -Headers $headers
    $indexJson = $indexDef | ConvertTo-Json -Depth 10

    # Save to blob storage
    $blobName = "$($index.name)-definition.json"

    $indexJson | Out-File -FilePath "temp-index.json" -Encoding UTF8
    Set-AzStorageBlobContent -Context $ctx -Container "index-definitions" -Blob $blobName -File "temp-index.json" -Force
    Remove-Item "temp-index.json" -Force
    Write-Host "Index $($index.name) backed up successfully"
}

Write-Host "All indexes backed up to storage account: $StorageAccountName"

# ================================================================