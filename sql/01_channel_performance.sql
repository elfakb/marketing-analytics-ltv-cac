-- 01 | Channel performance with all core KPIs
-- Dialect: SQLite (also runs on DuckDB / Postgres with minor changes)
WITH perf AS (
    SELECT channel,
           SUM(spend)         AS spend,
           SUM(impressions)   AS impressions,
           SUM(clicks)        AS clicks,
           SUM(leads)         AS leads,
           SUM(conversions)   AS conversions,
           SUM(new_customers) AS new_customers,
           SUM(revenue)       AS revenue,
           SUM(cogs)          AS cogs
    FROM campaigns_daily
    GROUP BY channel
)
SELECT channel,
       ROUND(spend, 0)                                         AS spend,
       ROUND(revenue, 0)                                       AS revenue,
       ROUND(revenue - cogs - spend, 0)                        AS profit,
       conversions,
       new_customers,
       ROUND(1.0 * clicks / impressions * 100, 2)              AS ctr_pct,
       ROUND(spend / NULLIF(clicks, 0), 2)                     AS cpc,
       ROUND(spend / NULLIF(leads, 0), 2)                      AS cpl,
       ROUND(spend / NULLIF(conversions, 0), 2)                AS cpa,
       ROUND(1.0 * conversions / clicks * 100, 2)              AS conv_rate_pct,
       ROUND(spend / NULLIF(new_customers, 0), 2)              AS cac,
       ROUND(revenue / NULLIF(spend, 0), 2)                    AS roas   -- NULL for Organic (no spend)
FROM perf
ORDER BY profit DESC;
