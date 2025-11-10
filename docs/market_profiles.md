## Market Profile Workflow

1. **Generate a profile skeleton**

   ```bash
   python scripts/set_market.py \
     --symbol ICP \
     --balance-usd 30 \
     --sizing-multiplier 1.0 \
     --profile-out profiles/market_102.yaml
   ```

   Review the generated file and tweak spread, volatility multipliers, guard rails, etc.

2. **Apply the profile**

   ```bash
   python scripts/apply_profile.py \
     --profile profiles/market_102.yaml \
     --config config.yaml \
     --metadata-out data/instruments/market_102.json
   ```

   Redeploy (update Railway env vars if required) to make the changes live.

3. **Iterate**

   When you retune values, edit the profile, then re-run `apply_profile.py`. The active `config.yaml` stays in sync and the metadata cache records the most recent exchange parameters.

