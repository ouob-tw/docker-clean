"""Small modal surfaces for help and cleanup results."""
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from .scrolling import ContainedVerticalScroll
from .engine import Image
from .widgets import ActionButton as Button


class DialogScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    DialogScreen { align: center middle; background: transparent; }
    .dialog-panel {
        width: 90%; height: 85%; padding: 1 2;
        border: solid $foreground; background: $surface; color: $foreground;
    }
    .dialog-title { height: 1; text-style: bold; margin-bottom: 1; }
    .dialog-body { height: 1fr; }
    .dialog-close { margin-top: 1; }
    """


class HelpScreen(DialogScreen):
    BINDINGS = [("escape", "close", "關閉")]

    def __init__(self, whitelist: bool) -> None:
        super().__init__()
        self.whitelist = whitelist

    def compose(self) -> ComposeResult:
        rules = (
            "Image Delete 刪除規則：每行一條 Regex，任一條命中完整 tag 就勾選整個 image；空白行忽略。\n"
            "輸入框預設兩行，最多四行，超過後在框內捲動。\n"
            "Regex 篩選只改變顯示，不改變勾選；「顯示全部」解除篩選並保留 Regex 與勾選。\n"
            "無 tag 顯示 None，可用 ^None$ 篩選或 Regex 勾選；.* 也包含無 tag 項目。\n"
            "同一 image 的全部 tag 都在刪除範圍內。\n"
            "預覽表格包含全部已勾選項目，不受篩選限制；可取消勾選或勾回原項目。\n"
            "動作原因顯示容器引用；詳細資料可查看完整 ID 與全部 tag。\n"
            "確認後按完整 ID 強制刪除，不停止或刪除容器。"
            if self.whitelist else
            "Keep：設定哪些映像（image）要保留，再清理其餘項目。\n\n"
            "操作順序\n"
            "1. 在清單勾選想保留的映像。只勾選還不會加入保留規則。\n"
            "2. 按「加入保留規則」，把勾選映像的標籤（tag）加入上方規則框。\n"
            "3. 按「儲存」，保存整個規則框與清理選項。\n"
            "4. 按「預覽」查看哪些會保留、哪些會刪除，檢查後再按「確認刪除」。\n\n"
            "加入保留規則會做什麼？\n"
            "例如勾選 nginx:latest，會加入 ^nginx:latest$，表示保留這個完整標籤。\n"
            "一個映像有多個標籤，就各加一條；沒有標籤的映像會略過。加入後仍需儲存。\n"
            "規則記住的是標籤名稱；同一映像只要有一個標籤符合，就會保留整個映像。\n\n"
            "也可以自己編輯規則\n"
            "每行一條正規表示式（Python Regex），符合其中一條就保留。\n"
            "例如 ^nginx: 可保留 nginx 的所有版本；^nginx:latest$ 只比對這個完整標籤。\n"
            "規則用 Python re.search 搜尋完整標籤文字；修改後請儲存，再重新預覽。\n\n"
            "清理選項\n"
            "預設跳過仍被容器使用的映像，包含已停止的容器。\n"
            "「強制刪除 image」會把這些映像也列入清理，但 Docker 仍可能拒絕刪除。\n"
            "「逐一移除標籤」會逐個移除待清理映像的標籤；移除最後一個時可能連映像一起刪除。\n"
            "符合保留規則的映像仍會保留。預覽可查看完整 ID、所有標籤及使用它的容器。"
        )
        with Vertical(classes="dialog-panel"):
            yield Static("使用說明", classes="dialog-title")
            with ContainedVerticalScroll(classes="dialog-body"):
                yield Static(rules + "\n\n"
                             "Space／Enter 可操作聚焦的按鈕，或切換表格勾選；點欄位標題切換升冪／降冪。\n"
                             "執行期間不能取消；進度與詳細 log 顯示在懸浮視窗，舊紀錄在上、新紀錄在下。\n"
                             "在 log 底部會跟進新紀錄，往上閱讀時保留位置。\n\n"
                             "Ctrl+Q 離開　Ctrl+P 命令選單　Ctrl+T 切換主題　Esc 關閉說明",
                             id="help-content", markup=False)
            yield Button("關閉", id="close-help", classes="dialog-close")

    def action_close(self) -> None:
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_close()


class ImageDetails(DialogScreen):
    BINDINGS = [("escape", "close", "關閉")]

    def __init__(self, image: Image) -> None:
        super().__init__()
        self.image = image

    def compose(self) -> ComposeResult:
        image = self.image
        refs = "\n".join(f"{ref.name} ({ref.status}) — {ref.id}" for ref in image.references) or "無"
        with Vertical(classes="dialog-panel"):
            yield Static("Image 詳細資料", classes="dialog-title")
            with ContainedVerticalScroll(classes="dialog-body"):
                yield Static(f"完整 ID：{image.id}\n\n"
                             f"全部 tag：\n{chr(10).join(image.tags) or 'None'}\n\n"
                             f"容器引用：\n{refs}\n\n"
                             f"大小：{image.size} bytes\n建立：{image.created}",
                             id="image-details", markup=False)
            yield Button("關閉", id="close-details", classes="dialog-close")

    def action_close(self) -> None:
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_close()
