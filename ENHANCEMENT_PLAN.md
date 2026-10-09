# engkit — Enhancement Plan (v0.2)

> **Người đọc:** chủ repo và các agent Claude Code thực thi plan
> **Trạng thái:** Draft. Phải chốt các câu hỏi mở ở §2.2 trước khi bắt đầu phase bị chặn.
> **Baseline:** code hiện tại, 131 test pass. Core khoảng 1.250 dòng, M6 khoảng 2.250 dòng (`src/engkit`).

## 1. Mục tiêu

| Tiêu chí | Cách đo khi xong |
|---|---|
| Gọn nhẹ | `src/engkit` ≤ 1.800 dòng sau P2–P4. Runtime dependency vẫn chỉ có PyYAML. |
| Ổn định với nhiều model | Mỗi `SKILL.md` ≤ 120 dòng. Có section "When to ask". Có trigger eval và kết quả thật trên ít nhất 2 model. |
| Không assume | Skill và agent dừng lại hỏi khi thiếu thông tin. Plan này cũng có §2.2 cho những chỗ chưa chắc. |
| Code sạch | Đạt các quy tắc ở §3. Review không còn tên viết tắt, không lồng quá 2 cấp. |
| Tối ưu token | Agent chỉ đọc file được giao. Model được chọn theo §4. |
| Install nhiều loại skill | Cài được skill built-in và skill từ git URL. Có lock, `update`, `uninstall`. |
| Bộ nhớ theo project | Skill `project-memory` cùng `.engkit/memory/`, lưu local, không commit. |

## 2. Quyết định

### 2.1 Đã chốt (user, 2026-10-09)

1. **Nguồn skill:** cài được từ git/URL. Chỉ dùng network khi lệnh thật sự cần, toolkit không còn offline hoàn toàn.
2. **Memory:** do skill và file markdown đảm nhiệm. Agent đọc và ghi theo quy tắc của skill. CLI chỉ hỗ trợ `init` và `validate`, không gọi model.
3. **Memory không commit:** chỉ nằm local trên máy từng người.
4. **M6:** thu gọn mạnh.

### 2.2 Câu hỏi mở (chưa chốt thì không làm phase tương ứng)

| # | Câu hỏi | Chặn | Đề xuất |
|---|---|---|---|
| Q1 | Cắt M6 đến mức nào? **A:** xoá toàn bộ code M6 (profiles, resolution, detection, packs, generation, define, schemas, stacks, templates), chỉ giữ 2 skill `project-discovery` và `stack-selection`; kết quả discovery ghi vào memory. **B:** như A nhưng giữ `project inspect` read-only, khoảng 150 dòng, không packs. | P2 | A |
| Q2 | `.engkit/skills.lock.json` của project có được commit không? | P4 | Có, để team cài lại giống nhau |
| Q3 | Cài từ remote có cần xác nhận không? | P4 | Lần chạy đầu chỉ hiện preview (commit, file list, file thực thi). Phải chạy lại với `--yes` mới cài thật. |
| Q4 | Nguồn remote hỗ trợ những dạng nào? | P4 | Chỉ git URL (https/ssh) kèm `--ref` và `--path`. Không hỗ trợ archive `.zip`/`.tar.gz`. |
| Q5 | Có thêm `ruff` làm dev dependency không (cần cài package)? | P1 | Có, chỉ dùng khi dev, không phải runtime |
| Q6 | Có `git init` và commit baseline trước khi sửa không? | P0 | Có, bắt buộc, vì P2 xoá nhiều code |

## 3. Coding rules

- Tên đầy đủ, không viết tắt: `component` thay cho `comp`, `diagnostics` thay cho `diags`, `explicit_component` thay cho `ec`. Ngoại lệ: `i` trong vòng lặp ngắn, `path`, `exc`.
- Mỗi hàm làm một việc. Thường ≤ 40 dòng, lồng tối đa 2 cấp. Dùng early return thay cho `if` lồng.
- Không lồng comprehension, không dùng ternary trong ternary, không chuỗi điều kiện dài trên một dòng.
- Comment chỉ giải thích *vì sao* khi điều đó không hiển nhiên. Không comment để nhắc lại code.
- Docstring tối đa 1 dòng, và chỉ viết cho hàm public mà tên chưa đủ nói rõ. Không lặp lại tham số và kiểu.
- Dòng ≤ 100 ký tự. Định dạng theo `ruff format` nếu Q5 được duyệt.
- Không thêm abstraction (class, registry, plugin) khi chưa có tối thiểu 2 nơi dùng thật.
- Dùng stdlib trước. Mỗi dependency mới phải được user duyệt.
- Mỗi thay đổi hành vi phải kèm test. Mỗi bug fix phải có test fail trước khi sửa.
- Giữ các invariant an toàn sẵn có: install staged và atomic, không ghi đè, không chạy script trong skill, test chỉ dùng thư mục tạm.

## 4. Quy tắc cho agent và phân model

**Chọn model**

| Loại việc | Model |
|---|---|
| Đổi tên, xoá code theo danh sách có sẵn, sửa docs, viết fixture | Haiku |
| Implement feature, viết test, refactor có logic | Sonnet |
| Thiết kế và review phần nhạy cảm (network, cài từ nguồn không tin cậy, update/uninstall) | Opus |
| Review cuối mỗi phase | 1 agent Sonnet. Riêng P4 thêm 1 agent Opus review bảo mật. |

**Tiết kiệm token**

- Mỗi agent nhận: mục tiêu, danh sách file được đọc và sửa, acceptance criteria. Không đưa nguyên plan.
- Agent không đọc `IMPLEMENTATION_PLAN.md` và `ENHANCEMENT_PLAN.md`, trừ khi task yêu cầu.
- Chỉ chạy song song các agent sửa những file khác nhau. Các agent sửa cùng file phải chạy tuần tự.
- Báo cáo của agent ≤ 15 dòng, gồm: file đã đổi, lệnh đã chạy và kết quả, việc còn tồn.
- Thiếu thông tin hoặc có 2 cách hiểu thì dừng lại và hỏi user, không đoán.

## 5. Phases

Thứ tự: P0 → P1 → P2 → (P3 và P4 làm song song được, vì sửa các module khác nhau) → P5 → P6.

### P0 — Baseline (Haiku)

- Sau khi user đồng ý (Q6): `git init`, commit trạng thái hiện tại.
- Ghi số liệu baseline vào `docs/metrics.md`: số dòng của từng module, số test, số dòng của từng `SKILL.md`.
- **Xong khi:** có commit baseline, có file metrics.

### P1 — Dọn code core và sửa tồn đọng (Sonnet)

Phạm vi: `cli`, `catalog`, `validator`, `installer`, `fsutil`, `platforms`, `resources`, `doctor`. Chỉ phần core, M6 để P2 xử lý.

- Áp dụng §3 cho các module trong phạm vi: đổi tên viết tắt, làm phẳng code lồng, bỏ comment thừa, rút gọn docstring.
- Sửa 4 issue còn tồn từ lần review trước:
  1. `tree_snapshot`: `os.walk` cần `onerror` để raise lỗi, không bỏ qua im lặng.
  2. Install vào thư mục `.claude/skills` là symlink phải bị refuse trước bước kiểm tra "already installed".
  3. Regex id dùng `fullmatch` hoặc `\Z`.
  4. `doctor`: `status_of` không được crash khi gặp thư mục không đọc được.
- **Không làm:** đổi hành vi CLI, thêm feature mới.
- **Xong khi:** test pass, có thêm test cho 4 issue, `ruff check` sạch (nếu Q5 được duyệt).

### P2 — Thu gọn M6 (Haiku xoá, Sonnet chỉnh skill)

Làm theo phương án được chọn ở Q1. Mô tả dưới đây là phương án A.

- Xoá `profiles`, `resolution`, `detection`, `packs`, `generation`, `define` và test của chúng. Xoá các thư mục `packs/`, `stacks/`, `schemas/`, `templates/`. Bỏ các lệnh `project *` và `stack *`, bỏ phần profile và generated trong `doctor`.
- Sửa `project-discovery`: kết quả (component, lệnh build/test, quy ước, unknowns) ghi vào memory dưới dạng entry `type: context`, theo P3.
- Sửa `stack-selection`: lựa chọn và lý do ghi thành entry `type: decision`.
- Cập nhật `setup.py` và `MANIFEST.in` để chỉ bundle `skills/`.
- Xoá eval của tính năng đã bỏ. Giữ eval của 2 skill.
- **Xong khi:** test pass, `src/engkit` ≤ 1.300 dòng, không còn tham chiếu nào đến module đã xoá (`grep` rỗng).

### P3 — Bộ nhớ làm việc theo project (Sonnet)

**Cấu trúc**

```text
.engkit/memory/
├── .gitignore        # nội dung "*": giữ memory local mà không sửa .gitignore của project
├── INDEX.md          # mỗi entry một dòng: "- [title](file.md) — type — tóm tắt"
└── <slug>.md         # mỗi file một fact
```

**Frontmatter của mỗi entry**

```yaml
---
name: payment-retry-policy          # trùng với tên file
type: decision                      # context | decision | convention | gotcha | task-state
status: verified                    # verified | hypothesis | assumption
updated: 2026-10-09                 # ngày tuyệt đối
sources: [src/payments/retry.py]    # path hoặc lệnh làm bằng chứng; có thể rỗng
---
```

**Skill `project-memory`** (≤ 120 dòng, đủ section bắt buộc)

- **Khi bắt đầu task:** đọc `INDEX.md`, chỉ mở những entry liên quan. Memory có thể đã cũ, nên kiểm tra lại với code trước khi dựa vào.
- **Khi kết thúc task:** chỉ ghi thông tin không suy ra được từ code hay git (quyết định và lý do, gotcha, trạng thái task dang dở). Có entry sẵn thì sửa, không tạo bản trùng. Entry sai thì xoá.
- **Không ghi:** secret, token, dữ liệu cá nhân, nội dung đã có trong code hoặc docs.
- Thiếu thông tin hoặc mâu thuẫn với code thì hỏi user, không tự chọn.

**CLI** (chỉ thêm 2 lệnh)

- `engkit memory init [--project-dir]`: tạo cấu trúc trên và không ghi đè. In ra đoạn snippet để user tự thêm vào `CLAUDE.md` (dòng `@.engkit/memory/INDEX.md`) và `AGENTS.md` (một dòng hướng dẫn đọc file). Không tự sửa 2 file đó.
- `engkit memory validate [--project-dir]`, kiểm tra:
  - frontmatter hợp lệ;
  - `INDEX.md` khớp với danh sách file;
  - `INDEX.md` ≤ 150 dòng, mỗi entry ≤ 60 dòng (để giữ token);
  - cảnh báo khi có chuỗi giống secret.
- `doctor`: thêm một dòng trạng thái memory.

**Cần ghi trong docs:** Claude Code đã có auto memory riêng. Memory của engkit là bản trung lập về platform, dùng chung cho Claude Code và Codex trong cùng project. Docs nên khuyên không ghi trùng ở hai nơi.

- **Xong khi:** test cho `init` (idempotent, không ghi đè) và cho `validate` (các trường hợp lỗi) đều pass. Skill qua `engkit validate`. Có 2 eval case: một cho việc nhớ lại quyết định cũ, một cho việc không ghi secret.

### P4 — Cài skill từ git (Opus thiết kế và review, Sonnet implement)

**CLI**

```bash
engkit list --source https://example.test/team/skills.git [--ref v1.2.0] [--path skills]
engkit install <name> --target claude                                  # built-in, như hiện tại
engkit install --source <git-url> [--ref REF] [--path DIR] --skill a --skill b --target all [--yes]
engkit update [<name>] [--target ...]
engkit uninstall <name> --target ...
```

**Fetch**

- Gọi `git` của hệ thống qua `subprocess` với argv list: `clone --depth 1 --no-recurse-submodules` vào thư mục tạm, xoá ngay sau khi xong.
- Đặt `GIT_TERMINAL_PROMPT=0` và có timeout.
- Ghi lại commit thật bằng `git rev-parse HEAD`.
- Chỉ những lệnh trên được dùng network. `validate`, `doctor` và `memory` vẫn offline.

**Nội dung không tin cậy**

- Validate chặt như skill built-in.
- Không bao giờ chạy file trong skill.
- Preview liệt kê các file có quyền thực thi hoặc nằm trong `scripts/`. Theo Q3, cần `--yes` mới cài.

**Lock** (`.engkit/skills.lock.json` cho project, `~/.engkit/skills.lock.json` cho global)

- Mỗi entry ghi: tên, `source` (`builtin` hoặc URL), ref, commit, `content_sha256`, các target đã cài.
- Skill built-in cũng ghi lock. Nhờ vậy bản built-in có đường để nâng cấp, giải quyết vấn đề "MVP không có đường nâng cấp" nêu trong lần review plan trước.

**`update` và `uninstall`**

- Chỉ thay hoặc xoá khi bản đang cài có hash đúng bằng hash trong lock, tức là user chưa sửa. Hash khác thì báo `conflict` và không đụng vào.
- Staging nằm ngoài thư mục skills. Có rollback khi đổi chỗ thất bại.

**Test**

- Repo git tạo trong thư mục tạm, truy cập qua `file://`. Không dùng internet.
- Bỏ qua test (skip) nếu máy không có `git`.
- Các tình huống cần cover: ref không tồn tại, skill không hợp lệ, symlink, cài lặp lại, update khi bản cài đã bị sửa, uninstall khi bản cài đã bị sửa.

- **Xong khi:** mọi test trên pass. Agent Opus review bảo mật không còn finding nào mức cao.

### P5 — Ổn định khi dùng với nhiều model (Sonnet viết, chạy eval thủ công)

- Thêm section bắt buộc **"When to ask"** vào contract và validator. Section này liệt kê các tình huống skill phải dừng lại hỏi user.
- Validator kiểm tra:
  - `SKILL.md` ≤ 120 dòng (vượt thì error, hiện tại chỉ warning ở 500 dòng);
  - `description` ≤ 1024 ký tự;
  - tên không trùng với tên skill built-in phổ biến của platform. Danh sách nằm trong `platforms`, cần verify với docs.
- Viết lại 6 skill (5 skill hiện có và `project-memory`):
  - mỗi bước là một hành động cụ thể;
  - output contract có template cố định;
  - không dựa vào suy luận ngầm của model mạnh.
- **Trigger eval:** mỗi skill có 5 prompt nên kích hoạt và 5 prompt không nên. Lưu ở `evals/triggers/`.
- **Chạy eval thủ công** trên ít nhất 2 model (ví dụ Haiku và Sonnet, cộng Codex nếu có), mỗi case 3 lần. Ghi `pass/fail/not-run` kèm model và version. Không bịa điểm.
- **Xong khi:** validator pass, có file kết quả eval thật hoặc được đánh dấu `not-run`.

### P6 — Docs và invariant (Haiku)

- Cập nhật `CLAUDE.md`:
  - invariant network: chỉ dùng trong `list --source`, `install --source` và `update`;
  - thêm invariant memory: local, không commit, không chứa secret;
  - thêm coding rules (tóm tắt §3);
  - cập nhật lệnh build/test.
- Cập nhật `README.md`, `docs/compatibility.md`, `docs/skill-authoring.md`. Đánh dấu các phần M6 trong `IMPLEMENTATION_PLAN.md` là superseded và trỏ sang file này.
- **Xong khi:** docs không còn nhắc tới lệnh hay module đã xoá. Quickstart trong README chạy được từ đầu đến cuối.

## 6. Kiến trúc sau enhance

| Module | Trách nhiệm | Ước lượng |
|---|---|---|
| `cli` | parse argument và in output | 250 dòng |
| `catalog` + `validator` | tìm skill, validate (dùng chung cho built-in và remote) | 280 dòng |
| `sources` *(mới)* | fetch skill từ git vào thư mục tạm | 120 dòng |
| `lockfile` *(mới)* | đọc và ghi lock | 80 dòng |
| `installer` | install, update, uninstall (staged, atomic) | 300 dòng |
| `memory` *(mới)* | `init` và `validate` | 120 dòng |
| `platforms`, `fsutil`, `resources`, `doctor` | giữ như hiện tại, đã dọn | 400 dòng |

## 7. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Skill remote chứa nội dung độc hại | Không chạy file trong skill, preview kèm `--yes`, validate chặt, ghi commit vào lock |
| Ref trên remote bị đổi nội dung | Lock ghi commit và hash. `update` báo rõ commit cũ và commit mới |
| Memory phình to, tốn token | Giới hạn kích thước trong `validate`. Skill yêu cầu update thay vì tạo mới, xoá entry sai |
| Memory cũ dẫn agent sai hướng | Skill bắt kiểm tra lại với code. Mỗi entry có `status` và `updated` |
| Xoá M6 làm mất tính năng có người đang dùng | Q1 phải chốt trước. Commit baseline ở P0 để có thể quay lại |
| Tên skill trùng với built-in của platform | Kiểm tra trong validator (P5) |

## 8. Ngoài phạm vi

Registry hay marketplace riêng, telemetry, MCP, gọi LLM API, cài artifact không phải skill (subagent, slash command), archive URL (trừ khi Q4 đổi), sync memory giữa các máy.
