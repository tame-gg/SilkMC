# Example SilkMC Server Setup

Example values:

- `motd=SilkMC | smooth, lightweight, compatibility-focused`
- pregenerated worlds for high player-count deployments
- enable compatibility warning mode first when migrating plugin packs

Suggested startup:

```powershell
java -Xms4G -Xmx4G -jar silkmc-paperclip.jar nogui
```

The `silkmc-server` module jar is not self-contained and should not be used as the end-user startup jar.
