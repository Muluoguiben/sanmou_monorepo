param(
  [Parameter(Position = 0)] [string]$Action,
  [Parameter(ValueFromRemainingArguments = $true)] [object[]]$LegacyArguments
)

# Deliberate tombstone: do not load Win32 code, elevate, install/trigger tasks,
# read command.json, launch executables, capture, or dispatch input.
# Existing installed copies are outside this repository and require a separate
# operator-managed retirement; this script must not modify them automatically.
[Console]::Error.WriteLine('SANMOU_LEGACY_CONTROLLER_DISABLED: user-writable Highest controller retired; use the capture-only observer or a separately reviewed trusted broker.')
exit 1
