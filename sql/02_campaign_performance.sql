-- 02 | Campaign ranking: revenue rank vs profit rank (they are NOT the same)
WITH perf AS (
    SELECT campaign_id, channel, campaign_name,
           SUM(spend) AS spend, SUM(revenue) AS revenue, SUM(cogs) AS cogs,
           SUM(conversions) AS conversions, SUM(new_customers) AS new_customers
    FROM campaigns_daily
    GROUP BY campaign_id, channel, campaign_name
), scored AS (
    SELECT *, revenue - cogs - spend AS profit FROM perf
)
SELECT campaign_id, channel, campaign_name,
       ROUND(spend, 0)   AS spend,
       ROUND(revenue, 0) AS revenue,
       ROUND(profit, 0)  AS profit,
       ROUND(revenue / NULLIF(spend, 0), 2) AS roas,
       RANK() OVER (ORDER BY revenue DESC)  AS revenue_rank,
       RANK() OVER (ORDER BY profit  DESC)  AS profit_rank,
       RANK() OVER (ORDER BY revenue DESC) - RANK() OVER (ORDER BY profit DESC) AS rank_shift
FROM scored
ORDER BY revenue_rank;
