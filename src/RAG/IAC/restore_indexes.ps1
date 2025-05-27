# restore-indexes.ps1 - Restore indexes after creation
param(
    [string]$ResourceGroupName = "rg-RAG",
    [string]$SearchServiceName = "aisearchbrochures",
    [string]$StorageAccountName = "searchindexbackup123"
)

# Get credentials
$adminKey = (Get-AzSearchAdminKeyPair -ResourceGroupName $ResourceGroupName -ServiceName $SearchServiceName).Primary
$storageKey = (Get-AzStorageAccountKey -ResourceGroupName $ResourceGroupName -Name $StorageAccountName)[0].Value
$ctx = New-AzStorageContext -StorageAccountName $StorageAccountName -StorageAccountKey $storageKey

# Get all backed up index definitions
$blobs = Get-AzStorageBlob -Context $ctx -Container "index-definitions" | Where-Object { $_.Name -like "*-definition.json" }

$headers = @{
    'api-key' = $adminKey
    'Content-Type' = 'application/json'
}

$searchEndpoint = "https://$SearchServiceName.search.windows.net"

foreach ($blob in $blobs) {
    Write-Host "Restoring index from: $($blob.Name)"

    # Download index definition
    Get-AzStorageBlobContent -Context $ctx -Container "index-definitions" -Blob $blob.Name -Destination "temp-index.json" -Force
    $indexDef = Get-Content "temp-index.json" | ConvertFrom-Json

    # Remove ALL read-only properties and include vector search config
    $cleanIndex = @{
        name = $indexDef.name
        fields = $indexDef.fields
        suggesters = $indexDef.suggesters
        corsOptions = $indexDef.corsOptions
        scoringProfiles = $indexDef.scoringProfiles
        analyzers = $indexDef.analyzers
        charFilters = $indexDef.charFilters
        tokenizers = $indexDef.tokenizers
        tokenFilters = $indexDef.tokenFilters
        defaultScoringProfile = $indexDef.defaultScoringProfile
        encryptionKey = $indexDef.encryptionKey
        similarity = $indexDef.similarity
        semantic = $indexDef.semantic
        vectorSearch = $indexDef.vectorSearch
    }

    # Remove null properties
    $cleanIndex = $cleanIndex.GetEnumerator() | Where-Object { $_.Value -ne $null } | ForEach-Object -Begin { $h = @{} } -Process { $h[$_.Key] = $_.Value } -End { $h }

    # Create index
    $indexName = $cleanIndex.name
    $body = $cleanIndex | ConvertTo-Json -Depth 10

    try {
        Write-Host "Creating index with body length: $($body.Length)"
        $uri = "$searchEndpoint/indexes/$indexName" + "?api-version=2023-11-01"
        Write-Host "Request URI: $uri"
        Invoke-RestMethod -Uri $uri -Method PUT -Headers $headers -Body $body
        Write-Host "Index $indexName restored successfully"
    }
    catch {
        Write-Host "Error details: $($_.Exception.Response.StatusDescription)"
        Write-Host "Full response: $($_.ErrorDetails.Message)"
        Write-Host "Request body preview: $($body.Substring(0, [Math]::Min(500, $body.Length)))"
        Write-Error "Failed to restore index $indexName"
    }
}

Remove-Item "temp-index.json" -ErrorAction SilentlyContinue
Write-Host "Index restoration complete"