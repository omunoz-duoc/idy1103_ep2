# EP2 evidence process — ELI5

Think of each query as a runner in a race:

- **A** is the original query.
- **B** is the rewritten query.
- **C** is exactly query B, but with one new index.

The Python program is the stopwatch and camera. You still need to prepare the track, make sure nobody else is using it, and explain what the pictures mean.

## What the program collects for you

For every A, B, or C run it saves:

- the exact query and parameters;
- `EXPLAIN FORMAT=TREE`;
- `EXPLAIN ANALYZE`;
- 2 warm-ups and 10 measured executions;
- minimum, mean, median, p95, maximum, and standard deviation;
- full query result and a SHA-256 result checksum;
- session counter changes, including scans, sorts, and temporary tables;
- all active indexes;
- MySQL version, time, connection, and database;
- Performance Schema information when the server permits access.

It does **not** invent conclusions. A person must inspect the evidence and explain it.

## Part 1 — One-time setup

### Step 1: Create an isolated database and load the dataset

Warning: `dataset.sql` drops and recreates all six EP2 tables. Use only a laboratory database.

Open MySQL:

```bash
mysql -u root -p
```

Then run:

```sql
CREATE DATABASE IF NOT EXISTS ep2_lab CHARACTER SET utf8mb4;
USE ep2_lab;
SOURCE /absolute/path/to/evaluacion_02/dataset.sql;
```

The supplied dataset already raises `cte_max_recursion_depth` in the same connection.

### Step 2: Save the dataset proof

From the project folder:

```bash
mysql -u root -p --table < sql/01_dataset_evidence.sql > evidencias/01_dataset.txt
```

Open `evidencias/01_dataset.txt`. Confirm at least:

- customers = 5,000;
- orders = 20,000;
- order items = 100,000.

If those three numbers are wrong, stop. Reload the dataset before benchmarking.

Save the MySQL configuration evidence too:

```bash
mysql -u root -p --table < sql/00_environment.sql > evidencias/00_mysql_environment.txt
```

Finally, update table statistics once and save the response:

```bash
mysql -u root -p --table < sql/02_prepare_baseline.sql > evidencias/02_analyze_initial.txt
```

Do not repeat this between A, B, and C unless you document it and apply the same rule to every phase.

### Step 3: Discover fixed parameter values

```bash
mysql -u root -p --table < sql/00_descubrir_parametros.sql
```

Copy the example:

```bash
cp sql/00_parametros.example.sql sql/00_parametros.sql
```

Edit `sql/00_parametros.sql`:

1. Copy the three dates printed by the discovery query.
2. Choose one printed `store_id`.
3. Confirm `CARD`, `Santiago`, `Retail`, and `RM` exist; otherwise use printed values that do exist.
4. Save the file and never change it between A, B, and C.

These values are not passwords and should be submitted with the evidence.

### Step 4: Record the computer by hand

Copy `00_entorno.template.md` to `00_entorno.md` and fill it in. This is manual because MySQL cannot reliably know the physical computer, Docker/WSL limits, disk type, or whether classmates are using the server.

Also note whether MySQL is local, Docker, or remote. Never put a password in this file.

### Step 5: Install the runner in a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r automation/requirements.txt
```

Windows PowerShell activation is:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r automation/requirements.txt
```

Set connection details. The password stays in memory and is not written to the evidence:

```bash
export EP2_MYSQL_HOST=127.0.0.1
export EP2_MYSQL_PORT=3306
export EP2_MYSQL_USER=root
export EP2_MYSQL_DATABASE=ep2_lab
read -s -p "MySQL password: " EP2_MYSQL_PASSWORD; export EP2_MYSQL_PASSWORD; echo
```

PowerShell equivalent:

```powershell
$env:EP2_MYSQL_HOST="127.0.0.1"
$env:EP2_MYSQL_PORT="3306"
$env:EP2_MYSQL_USER="root"
$env:EP2_MYSQL_DATABASE="ep2_lab"
$env:EP2_MYSQL_PASSWORD=Read-Host "MySQL password" -MaskInput
```

### If `root` gives error 1698 / Access denied

On Ubuntu/Debian, MySQL often allows `root` only through `sudo mysql`. That is normal. Do not change the root authentication plugin just for this assignment. Create a user restricted to the laboratory database instead.

Open the administrative MySQL console:

```bash
sudo mysql
```

Inside MySQL, choose a new private password and run:

```sql
CREATE USER IF NOT EXISTS 'ep2_runner'@'localhost'
  IDENTIFIED BY 'REPLACE_WITH_A_PRIVATE_PASSWORD';
GRANT SELECT, INDEX ON ep2_lab.* TO 'ep2_runner'@'localhost';
SHOW GRANTS FOR 'ep2_runner'@'localhost';
EXIT;
```

`SELECT` lets the runner measure queries. `INDEX` lets you create and remove the stage-C indexes. The account has no access to other databases. Do not paste the real password into a file or screenshot.

Test it before running evidence:

```bash
mysql -h 127.0.0.1 -u ep2_runner -p ep2_lab -e "SELECT COUNT(*) FROM ep2_orders;"
```

Then replace the old environment values in the same terminal:

```bash
export EP2_MYSQL_HOST=127.0.0.1
export EP2_MYSQL_USER=ep2_runner
export EP2_MYSQL_DATABASE=ep2_lab
read -s -p "MySQL password: " EP2_MYSQL_PASSWORD; export EP2_MYSQL_PASSWORD; echo
```

If the command-line test fails too, return to `sudo mysql` and verify `SHOW GRANTS`. If the command-line test succeeds but Python fails, confirm you launched Python from the same terminal containing those exported variables.

## Part 2 — Collect query evidence

Start with Q1 only. Once Q1 works, repeat the same pattern for Q2–Q5.

### Step 6: Collect A (original query)

Make sure no experimental index from `sql/03_indices.sql` exists. In MySQL, use `SHOW INDEX FROM ep2_orders;` and `SHOW INDEX FROM ep2_payments;`. Names beginning with `idx_ep2_q` are experimental and must not exist during A or B. Then run:

```bash
python automation/evidence_runner.py \
  --case Q1 --stage A \
  --query queries/Q1_A.sql \
  --params sql/00_parametros.sql
```

Do the same for Q2–Q5 by changing both occurrences of the query number.

Or collect all five A cases automatically:

```bash
python automation/run_stage.py --stage A
```

### Step 7: Collect B (rewritten query, still no experimental index)

```bash
python automation/evidence_runner.py \
  --case Q1 --stage B \
  --query queries/Q1_B.sql \
  --params sql/00_parametros.sql
```

Again, repeat for Q2–Q5. There must still be no experimental C index.

Or collect all five B cases automatically:

```bash
python automation/run_stage.py --stage B
```

Stages A and B are batchable because they must use only the original indexes. Stage C stays one-at-a-time to prevent indexes from different experiments contaminating each other.

### Step 8: Collect C, one case at a time

Use the safe stage-C command:

```bash
python automation/run_stage_c.py --case Q1
```

This command performs four steps:

1. It refuses to start if any old `idx_ep2_q...` index exists.
2. It creates and verifies Q1's experimental index.
3. It collects C using `Q1_B.sql`, because the query must not change between B and C.
4. It removes the index afterward, even if evidence collection fails.

For Q1, Q4, and Q5, MySQL may automatically replace an implicit foreign-key index with the wider experimental index. Before cleanup, the script restores the original one-column FK-supporting index, then removes the experimental index.

If an older run stopped during cleanup, repair it without rerunning evidence:

```bash
python automation/run_stage_c.py --case Q1 --cleanup-only
```

Repeat one case at a time:

```bash
python automation/run_stage_c.py --case Q2
python automation/run_stage_c.py --case Q3
python automation/run_stage_c.py --case Q4
python automation/run_stage_c.py --case Q5
```

`sql/03_indices.sql` remains a readable record of the DDL for the report. Its statements are comments intentionally; running that file directly does not create anything.

The runner's `Qn_C_indexes.csv` proves which index existed during the measurement. Open it and confirm the intended `idx_ep2_qn...` index is present and no other experimental index is present.

### Step 9: Build the comparison table

```bash
python automation/summarize_evidence.py
```

This creates `resultados_comparativos.csv`. Check that `same_result_as_A` is `true` for B and C. If it says `false`, do not claim an optimization—the query result changed and must be investigated.

## Part 3 — Evidence you still collect manually

### Manual item 1: Screenshots requested by the rubric

Text files are stronger reproducible evidence, but the rubric also asks for captures. Take clearly labelled screenshots of:

1. The required table counts in `evidencias/01_dataset.txt` or your SQL client.
2. Each selected query's A plan (`Qn_A_tree.txt` or the SQL client).
3. Each selected query's C plan (`Qn_C_tree.txt`).
4. The final A/B/C comparison table.

At minimum the assignment requires two queries. The guide proposes five. Do not submit an unlabeled screenshot: include query number, stage, and date in the filename or caption.

### Manual item 2: Make the test fair

Before each batch:

1. Close heavy programs and downloads when practical.
2. Check that nobody else is stressing the MySQL server.
3. Keep the same computer, server, network, parameter file, warm-up count, and iteration count.
4. Do not restart MySQL between A/B/C unless you restart it for every phase and document it.
5. Record any interruption or unusual load in `00_entorno.md`.

### Manual item 3: CPU, RAM, and disk I/O for sustained load

One query is usually too short for a useful OS screenshot. If the report requires OS monitoring, run a longer, fixed-size batch while monitoring the MySQL process.

Linux/WSL example:

```bash
pgrep -a mysqld
pidstat -u -r -d -p MYSQL_PID 1 | tee evidencias/Q1_A_os_pidstat.txt
```

Start `pidstat`, then run a larger evidence batch in another terminal. Use a separate output folder so the sustained-load run does not overwrite the 10-iteration microbenchmark:

```bash
python automation/evidence_runner.py \
  --case Q1 --stage A \
  --query queries/Q1_A.sql \
  --params sql/00_parametros.sql \
  --iterations 1000 \
  --output evidencias_carga
```

Stop `pidstat` with Ctrl+C when the runner finishes. Use the same iteration count for A/B/C. For Docker, use `docker stats`; for Windows, use Performance Monitor. Explain that these are batch-level measurements, not exact CPU for one statement.

### Manual item 4: Explain two observable causes per query

For every selected query, open its A files and write down two things you can actually see. Examples:

- A plan says `Table scan`.
- A plan contains `Sort`.
- `ROWS_EXAMINED` is much larger than `ROWS_SENT`.
- The plan loops over many order items.
- Session counters show temporary tables or many sequential reads.

Do not write “missing index” merely because it sounds plausible. First check `Qn_A_indexes.csv`. Foreign keys may already have supporting indexes.

### Manual item 5: Explain what changed and the trade-off

Compare A → B to explain the rewrite, then B → C to explain the index. Record:

- whether the access method, sort, rows, or loops changed;
- median and p95 time, not only the fastest run;
- whether the result checksums remained equal;
- whether the improvement was small or negative;
- index risks: extra disk space and slower inserts/updates/deletes.

A negative result is valid evidence. Do not claim that a plan cost is milliseconds, that rows are disk pages, or that global CPU belongs entirely to one query.

## Quick “am I finished?” checklist

- [ ] Dataset counts are correct and saved.
- [ ] Fixed parameters are real values from this dataset.
- [ ] Environment/hardware form is complete.
- [ ] A, B, and C evidence exists for each selected query.
- [ ] Only the current case's C index existed during C.
- [ ] B and C checksums equal A.
- [ ] Comparison CSV was generated.
- [ ] Required screenshots are labelled.
- [ ] Two observed causes are explained for every query.
- [ ] Results, limitations, index risk, and two future improvements are written.
- [ ] No password appears anywhere in the submission.
