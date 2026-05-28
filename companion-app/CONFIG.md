# Xcode Config

## Info.plist keys

Add these keys:

- `Privacy - Health Share Usage Description`
  - Example: `This app reads your health and workout data to update your private training dashboard.`
- `Privacy - Health Update Usage Description`
  - Example: `This app may write limited workout metadata in the future if you enable it.`
- `BGTaskSchedulerPermittedIdentifiers`
  - `toni.healthsync.refresh`

## Capabilities

Enable:

- `HealthKit`
- `HealthKit > Background Delivery`
- `Background Modes`
  - `Background fetch`
  - `Background processing`

## Deployment notes

- iOS target: `17.0+` recommended
- Set your Team in Signing & Capabilities
- Use automatic signing

## Endpoint

For the local bridge in this repo:

```text
http://YOUR-MAC-IP:8765/api/live-health
```

For a hosted backend later:

```text
https://your-domain.example/api/live-health
```
