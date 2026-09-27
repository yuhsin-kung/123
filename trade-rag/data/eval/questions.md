# 評測題（第一批）

| id | question | expect_file | expect_ok | notes |
| --- | --- | --- | --- | --- |
| Q1 | 盤中破前高會不會成交？ | RULE-001_timing_and_limits.md | yes | 只預警不成交 |
| Q2 | 台指期夜盤會不會進場？ | RULE-001_timing_and_limits.md | yes | 只看盤 |
| Q3 | severe 熱度時新倉預算池是現金多少％？ | RULE-002_news_budget_pool.md | yes | 2% |
| Q4 | 普通關稅升溫是硬關還是減碼？ | RULE-002_news_budget_pool.md | yes | 減碼／縮池 |
| Q5 | hot／severe 且當日收黑會怎樣？ | RULE-003_hard_stop.md | yes | 硬關，不能新買 |
| Q6 | hot／severe 但盤沒崩、也沒戰爭級？ | RULE-003_hard_stop.md | yes | 軟關，最多新開 1 檔 |
| Q7 | 預設先試幾股？買不起呢？ | RULE-004_lot_size.md | yes | 5→1→跳過 |
| Q8 | 進場要破幾日高、SNR 門檻？ | RULE-005_entry_exit.md | yes | 20 日、0.40 |
