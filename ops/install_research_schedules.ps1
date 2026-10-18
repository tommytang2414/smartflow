$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonExecutable = 'C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) { throw 'Verified operator Python is unavailable' }
if ((Get-TimeZone).BaseUtcOffset -ne [TimeSpan]::FromHours(8)) { throw 'Inspect task timezone before installing HKT schedule' }
$taskNames = @('SmartFlowResearchRefresh', 'SmartFlowResearchDrain')
foreach ($taskName in $taskNames) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw "Existing task requires inspection: $taskName" }
}
$gatewayRoot = Join-Path $projectRoot 'data\research-prototype\gateway'
$aliasPath = Join-Path $projectRoot 'config\research-aliases-us.json'
if (-not (Test-Path -LiteralPath $aliasPath)) { throw 'Verified research alias file is required' }
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$refresh = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(10).AddMinutes(15))
$nextDrain = [datetime]::Now.Date.AddHours([datetime]::Now.Hour).AddMinutes(25)
if ($nextDrain -le [datetime]::Now) { $nextDrain = $nextDrain.AddHours(1) }
$drain = New-ScheduledTaskTrigger -Once -At $nextDrain -RepetitionInterval (New-TimeSpan -Hours 1)
foreach ($taskMode in @(@('refresh', $refresh, $taskNames[0]), @('drain', $drain, $taskNames[1]))) {
    $taskArguments = '-X utf8 -m smartflow.research.gateway ' + $taskMode[0] + ' --root "' + $gatewayRoot + '" --aliases "' + $aliasPath + '"'
    $action = New-ScheduledTaskAction -Execute $pythonExecutable -Argument $taskArguments -WorkingDirectory $projectRoot
    Register-ScheduledTask -TaskName $taskMode[2] -Action $action -Trigger $taskMode[1] -Settings $settings -Principal $principal -Description 'Approved SmartFlow existing-auth input/backup/self-mail gateway; requires interactive Windows and pinned Mac LAN.' | Out-Null
    Export-ScheduledTask -TaskName $taskMode[2] | Set-Content -LiteralPath (Join-Path $gatewayRoot ($taskMode[2] + '.xml')) -Encoding UTF8
}
Get-ScheduledTask -TaskName $taskNames | Select-Object TaskName, State, Principal, Actions, Triggers
