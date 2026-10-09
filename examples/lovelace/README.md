# Dashboard examples

## PQ1 schedules

[PQ1_SCHEDULE_CARD.yaml](PQ1_SCHEDULE_CARD.yaml) displays saved schedule entries,
Remaining Time and inferred Current Work Mode, including the SOC cut-off notice.
It uses Home Assistant's built-in Markdown card and requires no custom card.

1. Open your dashboard, select **Edit dashboard**, then **Add card → Manual**.
2. Paste the complete YAML file.
3. Adjust the four entity IDs at the top to match your inverter's prefix.
4. Save the card. Enable the referenced entities if they are disabled.

The card is read-only. Change schedules in the FOX Cloud App.
