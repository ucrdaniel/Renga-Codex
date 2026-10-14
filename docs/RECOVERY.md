# Тайм-ауты и восстановление / Timeouts and recovery

## Что делает ограниченный supervisor

CLI и MCP запускают операции в отдельном STA worker. Supervisor работает как
watchdog этой команды: по умолчанию её предел — 180 секунд. CLI `--timeout` или
`RENGA_BRIDGE_COMMAND_TIMEOUT_SEC` принимает конечное значение от 1 до 3600 секунд.
Тайм-аут клиента MCP должен быть больше этого предела с запасом на очистку;
каждое подтверждённое завершение процесса ожидается не более пяти секунд.
Это контроль конкретной команды, а не независимая постоянно работающая служба.

Перед отправкой команды supervisor создаёт приватный ownership-манифест и
записывает PID, точное Windows FILETIME создания и executable запускаемого
интерпретатора. Windows `.venv\Scripts\python.exe` может быть redirector:
реальный Python worker является его дочерним процессом. Worker доказывает эту
цепочку и записывает собственную identity **до COM-операций**. Новый Renga PID
добавляется только после получения HWND и отказа от всех PID, существовавших
до COM-активации.

При тайм-ауте останавливается запущенный этой командой launcher. Затем ownership
helper проверяет identity реального worker и завершает его, после чего проверяет
и завершает только подтверждённую собственную Renga. Проверка PID, времени
создания и executable и завершение используют один удерживаемый kernel handle:
повторное использование PID не разрешает завершать новый чужой процесс.
Завершения по имени `Renga.exe`, массового завершения и подключения к
пользовательскому COM-сеансу нет.

Если тайм-аут произошёл внутри активации COM или получения HWND, Renga PID может
ещё отсутствовать в манифесте. В таком случае мост **не может безопасно завершить
эту Renga автоматически**. Некорректный манифест, отказ доступа или изменившаяся
identity также приводят к отказу от неподтверждённого завершения. Если завершился
сам supervisor, автоматическая очистка не гарантирована. Манифест — локальное
свидетельство, а не защита от вредоносного процесса того же пользователя Windows.

## Значение `outcome: unknown`

Даже успешное принудительное завершение не доказывает откат, сохранность или
полноту BIM-модели. Операция могла остановиться до Save, во время записи или
после неё. Сообщение timeout не равно «изменения отменены». Перед повторением
нужно прочитать сохранённый результат и сопоставить его с исходным планом.

Локальные свидетельства находятся в `RENGA_BRIDGE_STATE_ROOT`, по умолчанию
`%LOCALAPPDATA%\Renga-Codex-Bridge`:

- `operations.jsonl` — запросы, предварительные setters, проверенные записи,
  ошибки и timeout cleanup;
- `ownership/` — manifests с PID/creation-time и состояниями процессов;
- `plans/` — исходные JSON-планы;
- `backups/` — копии существовавших файлов с проверенным SHA-256.

Путь без COM можно уточнить командой:

```powershell
.\.venv\Scripts\python.exe -c "from renga_codex_bridge.config import settings; print(settings().state_root)"
```

Не публикуйте эти каталоги: журналы и резервные копии могут содержать пути,
модели и проектные сведения.

## Последовательность восстановления

1. Прекратите повторять команду. Сохраните журналы, манифест, исходный план,
   существующий результат и резервные копии.
2. Проверьте запись timeout: какие процессы действительно завершены, какие уже
   вышли и для каких cleanup отказал. Числового PID или имени процесса достаточно
   только для поиска, а не для доказательства владения. Не завершайте чужую Renga.
3. Если файл сохранился, прочитайте его в **новом отдельном сеансе** моста.
   Сравните постоянные UUID, параметры, геометрию и площади с планом. Успешный
   `inspect` подтверждает чтение; он не заменяет эти предметные проверки.
4. Если требуется восстановление, сначала проверьте SHA-256 выбранной backup
   по записи `backup`. Создайте из неё новый файл внутри разрешённой тестовой
   папки и проверьте его повторным открытием. Эта копия оставляет аварийный
   результат доступным для анализа.
5. Перезапись исходного файла backup-копией требует явного разрешения владельца
   для этого файла и сохранения текущего результата отдельно. Мост не выполняет
   автоматическое восстановление поверх оригинала.
6. Повторите только недостающие операции после проверки фактического состояния.
   Повтор целого плана создания может добавить дубликаты. Для ошибок setter
   проверяйте именно сохранённые значения, а не отсутствие исключения.

Renga undo применяется к model objects. SDK не гарантирует undo для project-based
entities; резервная копия нужна и для редактирования сведений проекта. Не
восстанавливайте результат через пользовательский несохранённый сеанс и не
удаляйте lock-файл активной команды, чтобы обойти сериализацию.

## English

Each CLI/MCP command has a bounded supervisor acting as its watchdog. The default
is 180 seconds; `--timeout`/`RENGA_BRIDGE_COMMAND_TIMEOUT_SEC` permits finite values
from 1 to 3600 seconds. Set the client deadline higher than the worker limit and
allow time for cleanup. This is not an independent always-running recovery daemon.

The private ownership manifest records the supervisor, observed launcher, actual
Python worker and verified isolated Renga PID with exact creation times and image
paths. A Windows venv redirector's child interpreter is proved before COM work.
After stopping the launcher, cleanup stops only the matching actual worker, then
matching Renga, using retained handles across verification and termination. PID
reuse, access denial or inconsistent evidence cause refusal, not a name-based kill.

Before a Renga HWND/PID is recorded, the COM server cannot be terminated safely
by this mechanism. A supervisor crash can also leave cleanup incomplete. Local
manifests are recovery evidence, not a boundary against hostile same-user code.

`outcome: unknown` always means that rollback and saved BIM integrity were not
proved, even if process termination succeeded. Keep the operation log, manifests,
plans, existing result and backups. Reopen the saved file in a new isolated bridge
session and compare persistent IDs, values and geometry with the plan. Do not
attach to the user's session or stop unrelated Renga processes.

Verify a backup's SHA-256 against its audit record, copy it to a **new** disposable
project, and reopen/check that copy before deciding to restore an original.
Overwriting an original requires explicit file-specific authorization and keeping
the current result separately. There is no automatic restore over user files.
Retry only operations still needed after inspecting actual state; blindly
replaying creation plans can duplicate elements. Project metadata undo is not
guaranteed by SDK model-object undo rules; preserve verified backups.

State lives in `RENGA_BRIDGE_STATE_ROOT` (normally
`%LOCALAPPDATA%\Renga-Codex-Bridge`). Its logs, ownership records, plans and BIM
backups are private and must not be committed or uploaded without sanitizing.
