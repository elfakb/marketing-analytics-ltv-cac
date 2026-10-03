-- 03 | Which channel works in which customer segment?
-- Matured 90-day cohort only (signup <= 2025-10-03 => full 90 days observed).
-- Channel-level CAC is applied to every segment (spend is not observable by segment).
WITH cohort AS (
    SELECT cu.*, d.channel AS acq_channel
    FROM customers cu
    JOIN dim_campaign d ON d.campaign_id = cu.acquisition_campaign_id
    WHERE cu.ltv_90 IS NOT NULL
), channel_cac AS (
    SELECT d.channel,
           SUM(f.spend) / (SELECT COUNT(*) FROM cohort c WHERE c.acq_channel = d.channel) AS cac
    FROM campaigns_daily f
    JOIN dim_campaign d USING (campaign_id)
    WHERE f.date <= '2025-10-03'
    GROUP BY d.channel
)
SELECT c.acq_channel AS channel,
       c.segment,
       COUNT(*)                          AS customers,
       ROUND(AVG(c.ltv_90), 0)           AS ltv_90,
       ROUND(AVG(c.repeat_90) * 100, 1)  AS repeat_rate_pct,
       ROUND(k.cac, 0)                   AS channel_cac,
       ROUND(AVG(c.ltv_90) - k.cac, 0)   AS net_ltv_90
FROM cohort c
JOIN channel_cac k ON k.channel = c.acq_channel
GROUP BY c.acq_channel, c.segment
HAVING COUNT(*) >= 30                      -- ignore tiny cells
ORDER BY net_ltv_90 DESC;
