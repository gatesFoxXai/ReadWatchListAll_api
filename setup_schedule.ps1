# PowerShell script to schedule weekly execution of run.py at Monday 08:30
# Run this script as Administrator (required to register tasks for SYSTEM account)

# Define the path to the Python interpreter and the script
$pythonPath = "python"  # Assumes python is in PATH; adjust if needed
$scriptPath = "e:\workspace\OneAP_Python\run.py"

# Create the action that runs the script
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "\"$scriptPath\""

# Define a weekly trigger for Monday at 08:30
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 08:30

# Register the task (runs with highest privileges under SYSTEM account)
# Change -User if you prefer a specific user account.
Register-ScheduledTask -TaskName "OneAP_RunWeekly" -Action $action -Trigger $trigger -Description "Run OneAP weekly email task" -User "SYSTEM" -RunLevel Highest

Write-Host "Scheduled task 'OneAP_RunWeekly' has been created."
