-- 04 | High conversion but low LTV? (acquisition campaigns, matured 90-day cohort)
WITH conv AS (
    SELECT campaign_id, channel, campaign_name,
           1.0 * SUM(conversions) / SUM(clicks) AS cvr,
           SUM(spend) AS spend
    FROM campaigns_daily GROUP BY 1, 2, 3
), ltv AS (
    SELECT acquisition_campaign_id AS campaign_id,
           COUNT(*)      AS customers,
           AVG(ltv_90)   AS ltv_90,
           AVG(repeat_90) AS repeat_rate
    FROM customers WHERE ltv_90 IS NOT NULL
    GROUP BY 1
    HAVING COUNT(*) >= 100                 -- excludes Winback (no new customers)
), joined AS (
    SELECT c.*, l.customers, l.ltv_90, l.repeat_rate
    FROM conv c JOIN ltv l USING (campaign_id)
), thresholds AS (
    SELECT AVG(cvr) AS cvr_t, AVG(ltv_90) AS ltv_t FROM joined
)
SELECT j.campaign_id, j.channel, j.campaign_name,
       ROUND(j.cvr * 100, 2)         AS conv_rate_pct,
       ROUND(j.ltv_90, 0)            AS ltv_90,
       ROUND(j.repeat_rate * 100, 1) AS repeat_rate_pct,
       CASE WHEN j.cvr >= t.cvr_t AND j.ltv_90 <  t.ltv_t THEN 'Conversion trap'
            WHEN j.cvr >= t.cvr_t AND j.ltv_90 >= t.ltv_t THEN 'Star'
            WHEN j.cvr <  t.cvr_t AND j.ltv_90 >= t.ltv_t THEN 'Hidden gem'
            ELSE 'Underperformer' END AS quadrant
FROM joined j CROSS JOIN thresholds t
ORDER BY quadrant, ltv_90 DESC;
