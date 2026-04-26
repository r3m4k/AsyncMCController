# Сигналы по классам

Сводная таблица сигналов сигнальной шины (`signal_bus`) с разбивкой по классам.
Для каждого класса указаны две таблицы:

- **Принимает** — сигналы, обработчики которых класс регистрирует в `__init__`.
- **Эмиттит** — сигналы, которые класс отправляет в шину сам.

Базовые классы и их наследники разделены: в наследниках перечислены **только
дополнительные** сигналы, поверх унаследованных от родителя.

---

## byte_source

### `AsyncComPort(AsyncBytesSource)`

Низкоуровневый асинхронный COM-порт. Запускает / останавливает цикл чтения по
команде, эмиттит каждый прочитанный байт и сигнализирует об ошибках чтения.

**Принимает:**

| Сигнал | Назначение в классе |
|---|---|
| `START_MEASURING` | Запустить `reading_loop` (создать задачу чтения). |
| `STOP_MEASURING` | Отменить задачу `reading_loop` и дождаться её завершения. |

**Эмиттит:**

| Сигнал | Назначение в классе |
|---|---|
| `NEW_BYTE` | Эмиттится из `reading_loop` для каждого прочитанного байта. |
| `READ_ERROR` | Эмиттится из `reading_loop` при перехвате `ComPortReadError` (физический обрыв связи, ошибка драйвера и т.п.); цикл чтения завершается штатно, дальнейшую остановку выполняет `Controller`. |

---

### `AsyncComPortImu(AsyncComPort)`

Расширяет `AsyncComPort` IMU-протоколом: рукопожатие, heartbeat-цикл,
отправка команд с ожиданием подтверждения, аварийная остановка.

Унаследованные от `AsyncComPort` сигналы (`START_MEASURING`, `STOP_MEASURING`,
`NEW_BYTE`, `READ_ERROR`) сохраняются — `on_start_measuring` / `on_stop_measuring`
переопределены и в конце вызывают реализацию родителя.

**Принимает (дополнительно):**

| Сигнал | Назначение в классе |
|---|---|
| `HANDSHAKE_DONE` | Декодер принял ACK рукопожатия от МК — выставить `_handshake_event`, перевести плату в режим измерения, запустить heartbeat-loop. |
| `HEARTBEAT_ACK` | Декодер принял ACK heartbeat — выставить `_heartbeat_ack_event`, чтобы `_heartbeat_loop` вышел из ожидания. |
| `COMMAND_ACK` | Декодер принял подтверждение команды — выставить `_command_ack_event`, чтобы `_send_command_with_ack` вышел из ожидания. |
| `COMMAND_REJECTED` | Декодер принял от МК `'UNKNOWN_COMMAND'` — выставить тот же `_command_ack_event`, чтобы `_send_command_with_ack` вышел из ожидания без ложного `COMMAND_ACK_TIMEOUT` (исход уже доставлен наружу самим декодером). |
| `INTERRUPT_MEASURING` | `Controller` инициировал аварийную остановку — отменить heartbeat-loop, выставить `_command_ack_event` (чтобы зависший `_send_command_with_ack` мгновенно вышел), остановить чтение. Команды на МК не посылаются. Идемпотентен через флаг `_stopped`. |

**Эмиттит (дополнительно):**

| Сигнал | Назначение в классе |
|---|---|
| `HANDSHAKE_INIT` | Перед отправкой команды рукопожатия в `on_start_measuring` — оповещает декодер о начале работы с неизвестным МК, чтобы он сбросил накопленное состояние. |
| `HANDSHAKE_FAILED` | МК не прислал ACK рукопожатия за `_RESPONSE_TIMEOUT`. |
| `HEARTBEAT_SENT` | Перед отправкой heartbeat-команды (декодер сохраняет состояние FSM, чтобы корректно принять короткий ACK). |
| `DEVICE_LOST` | МК не прислал ACK heartbeat за `_RESPONSE_TIMEOUT` — устройство потеряно. |
| `COMMAND_SENT` | Перед отправкой команды с ожиданием подтверждения (декодер сохраняет состояние FSM). |
| `COMMAND_ACK_TIMEOUT` | МК не подтвердил команду за `_RESPONSE_TIMEOUT`. |

---

## decoding

### `BaseDecoder[T]` (ABC, Generic)

Универсальный конечный автомат разбора байтового потока с тремя очередями
(байты / готовые пакеты / корутины-команды) и тремя фоновыми задачами.

**Принимает:**

| Сигнал | Назначение в классе |
|---|---|
| `NEW_BYTE` | Положить полученный байт во внутреннюю `_byte_queue`, откуда его заберёт `_processing_loop` для обработки FSM. |
| `HANDSHAKE_INIT` | Начало работы с новым МК — вызвать `_clear()` и сбросить FSM, буфер посылки и счётчики. Очереди и фоновые задачи не пересоздаются (это безопасно вызывать из обработчика сигнала). |

**Эмиттит:**

| Сигнал | Назначение в классе |
|---|---|
| `PACKAGE_READY` | Эмиттится из `_package_emitting_loop` для каждого готового декодированного пакета типа `T`. |

---

### `ImuDecoder(BaseDecoder[ImuData])`

Расширяет `BaseDecoder` логикой IMU-протокола: распознаёт форматы пакетов
(данные / команда МК / текстовое сообщение), сохраняет состояние FSM на время
обработки коротких ACK-пакетов.

Унаследованные сигналы (`NEW_BYTE`, `HANDSHAKE_INIT`, `PACKAGE_READY`)
сохраняются. При `HANDSHAKE_INIT` через переопределённый `_clear()`
дополнительно очищаются `received_data` и `_saved_state`.

**Принимает (дополнительно):**

| Сигнал | Назначение в классе |
|---|---|
| `HEARTBEAT_SENT` | `AsyncComPortImu` собирается отправить heartbeat — сохранить состояние FSM (`_save_state`) и переключиться в `WantHeader`, чтобы корректно принять короткий ACK. |
| `COMMAND_SENT` | `AsyncComPortImu` собирается отправить команду с ACK — то же действие, сохранить состояние FSM. |
| `COMMAND_ACK_TIMEOUT` | МК не ответил на команду за таймаут — откатить `_saved_state` (через `_restore_state`), иначе следующий `on_command_sent` / `on_heartbeat_sent` перезапишет сохранённое состояние и оно будет потеряно. |

**Эмиттит (дополнительно):**

| Сигнал | Назначение в классе |
|---|---|
| `HANDSHAKE_DONE` | В `_bytes_to_message` принято `'IMU_STM32_ACK'`. |
| `HEARTBEAT_ACK` | В `_bytes_to_message` принято `'IMU_STM32_ALIVE'`; перед эмиссией восстанавливает `_saved_state`. |
| `COMMAND_ACK` | В `_bytes_to_message` принято `'CONFIRM_RECEIVED_COMMAND'`; перед эмиссией восстанавливает `_saved_state`. |
| `COMMAND_REJECTED` | В `_bytes_to_message` принято `'UNKNOWN_COMMAND'` — МК не распознал команду от ПК (программная ошибка контракта); перед эмиссией восстанавливает `_saved_state`. |

---

## controller

### `Controller`

Оркестратор жизненного цикла измерения. Запускает / штатно останавливает
измерение, реагирует на аварийные сигналы выставлением `_force_stop` и при
выходе из цикла ожидания решает, какой сигнал об остановке эмиттить.
Дополнительно выводит в консоль номер каждого принятого пакета.

**Принимает:**

| Сигнал | Назначение в классе |
|---|---|
| `PACKAGE_READY` | Вывести номер свежепринятого пакета через `\r` (одна перезаписываемая строка вместо тысяч дубликатов). |
| `READ_ERROR` | Цикл чтения в `AsyncComPort` упал на `ComPortReadError` — выставить `_force_stop`. Дальнейшую остановку ресурсов выполнит сам `Controller` через `INTERRUPT_MEASURING` из `stop()`. |
| `HANDSHAKE_FAILED` | Рукопожатие с МК не выполнено — выставить `_force_stop`. |
| `DEVICE_LOST` | МК не отвечает на heartbeat — выставить `_force_stop`. |
| `COMMAND_ACK_TIMEOUT` | МК не подтвердил команду — выставить `_force_stop`. |
| `COMMAND_REJECTED` | МК ответил `'UNKNOWN_COMMAND'` — программная ошибка контракта ПК↔МК; выставить `_force_stop`. |

**Эмиттит:**

| Сигнал | Назначение в классе |
|---|---|
| `START_MEASURING` | Из `start()` — запустить чтение и протокольное взаимодействие с МК. |
| `STOP_MEASURING` | Из `stop()` при штатном завершении (условие `check_condition()` стало `False`). |
| `INTERRUPT_MEASURING` | Из `stop()` при аварийном завершении (`_force_stop` выставлен), а также дополнительно после неудачной штатной остановки, если `_force_stop` выставился во время самой `STOP_MEASURING` (например, `COMMAND_ACK_TIMEOUT` при попытке перевести МК в холостой режим). |

---

## Сводная картина по сигналам

Кто эмиттит и кто подписан — для перекрёстной сверки.

**Принимающие классы по сигналам:**

| Сигнал | Подписан |
|---|---|
| `NEW_BYTE` | `BaseDecoder` |
| `PACKAGE_READY` | `Controller` |
| `START_MEASURING` | `AsyncComPort` *(переопр. в `AsyncComPortImu`)* |
| `STOP_MEASURING` | `AsyncComPort` *(переопр. в `AsyncComPortImu`)* |
| `INTERRUPT_MEASURING` | `AsyncComPortImu` |
| `READ_ERROR` | `Controller` |
| `HANDSHAKE_INIT` | `BaseDecoder` |
| `HANDSHAKE_DONE` | `AsyncComPortImu` |
| `HANDSHAKE_FAILED` | `Controller` |
| `HEARTBEAT_SENT` | `ImuDecoder` |
| `HEARTBEAT_ACK` | `AsyncComPortImu` |
| `DEVICE_LOST` | `Controller` |
| `COMMAND_SENT` | `ImuDecoder` |
| `COMMAND_ACK` | `AsyncComPortImu` |
| `COMMAND_ACK_TIMEOUT` | `ImuDecoder`, `Controller` |
| `COMMAND_REJECTED` | `AsyncComPortImu`, `Controller` |

**Эмиттирующие классы по сигналам:**

| Сигнал | Эмиттит |
|---|---|
| `NEW_BYTE` | `AsyncComPort` |
| `PACKAGE_READY` | `BaseDecoder` |
| `START_MEASURING` | `Controller` |
| `STOP_MEASURING` | `Controller` |
| `INTERRUPT_MEASURING` | `Controller` |
| `READ_ERROR` | `AsyncComPort` |
| `HANDSHAKE_INIT` | `AsyncComPortImu` |
| `HANDSHAKE_DONE` | `ImuDecoder` |
| `HANDSHAKE_FAILED` | `AsyncComPortImu` |
| `HEARTBEAT_SENT` | `AsyncComPortImu` |
| `HEARTBEAT_ACK` | `ImuDecoder` |
| `DEVICE_LOST` | `AsyncComPortImu` |
| `COMMAND_SENT` | `AsyncComPortImu` |
| `COMMAND_ACK` | `ImuDecoder` |
| `COMMAND_ACK_TIMEOUT` | `AsyncComPortImu` |
| `COMMAND_REJECTED` | `ImuDecoder` |
