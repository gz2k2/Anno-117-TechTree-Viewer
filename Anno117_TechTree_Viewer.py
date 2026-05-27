################################################################################
# IMPORTS
################################################################################

from __future__ import annotations

import copy
import json
import math
import sys
import typing as t
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from PyQt6.QtCore import QPointF, Qt, QRegularExpression, QUrl, QSize
from PyQt6.QtGui import QBrush, QColor, QDesktopServices, QFont, QIcon, QPen, QPixmap, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QDialog,
    QTextEdit,
    QGraphicsEllipseItem,
    QComboBox,
    QGraphicsRectItem,
    QCheckBox,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)



def _get_app_version() -> str:
    """Reads the version from version.txt for consistent UI labeling."""
    v_file = get_resource_path("version.txt")
    if v_file.exists():
        return v_file.read_text(encoding="utf-8").strip()
    return "unknown"


APP_NAME = f"Anno 117 TechTree Viewer v{_get_app_version()}"


################################################################################
# GLOBAL VARIABLES
################################################################################


CONFIG_FILE = "a117ttv_config.json"


################################################################################
# UTILITIES
################################################################################

def get_resource_path(relative_path: str | Path) -> Path:
    """
    Resolves the absolute path for resources. 
    Handles both normal execution and PyInstaller's temporary directory.
    """

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path

    return Path(__file__).parent / relative_path




################################################################################
# SETTINGS & CONFIG
################################################################################

class AppConfig:
    """Handles persistence of application settings."""

    def __init__(self):

        self.xml_root_path: str = ""
        self.category_offsets: dict[str, list[float]] = {
            "Civic": [0.0, 2.0, 3.0],
            "DLC01": [0.0, -1.0, 1.0],
            "Economy": [-4.0, 1.0, 1.0],
            "Military": [4.0, 1.0, 1.0],
        }

        if getattr(sys, "frozen", False):
            # Wenn kompiliert (EXE), Pfad der ausführbaren Datei nutzen
            base_dir = Path(sys.executable).parent

        else:
            base_dir = Path(__file__).parent

        self._path = base_dir / CONFIG_FILE


    def load(self) -> None:

        if not self._path.exists():
            return

        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                self.xml_root_path = data.get("xml_root_path", "")
                self.category_offsets = data.get("category_offsets", self.category_offsets)

        except Exception:
            pass

        return


    def save(self) -> None:

        data = {
            "xml_root_path": self.xml_root_path,
            "category_offsets": self.category_offsets,
        }

        try:
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

        except Exception:
            pass

        return




################################################################################
# DATA MODEL
################################################################################

@dataclass(frozen=True, slots=True)
class TechNode:
    guid: str
    name: str
    is_repeatable: bool
    is_gate: bool
    knowledge_needed: int | None
    repeatable_cost_factor: float | None
    grid_x: float
    raw_grid_x: int
    grid_y: float
    raw_grid_y: int
    color: str
    description: str | None
    tech_description: str | None
    unlock_reward_guid: str | None = None
    effect_asset_guid: str | None = None
    unlock_trigger_guids: tuple[str, ...] = ()




################################################################################
# XML PARSING
################################################################################


def _text_of(elem: ET.Element | None) -> str | None:

    if elem is None:
        return None

    text = elem.text
    if text is None:
        return None

    text = text.strip()

    return text if text else None


def _parse_int(value: str | None) -> int | None:

    if value is None:
        return None

    try:
        return int(value)

    except ValueError:

        return None


def _parse_float(value: str | None) -> float | None:

    if value is None:
        return None

    try:
        return float(value)

    except ValueError:

        return None


def _parse_description(
    text_map: dict[str, str] | None, tech: ET.Element | None
) -> str | None:

    if text_map is None or tech is None:
        return None

    visible_desc_id = _text_of(tech.find("VisibleTechDescription"))

    if not visible_desc_id:
        return None

    return text_map.get(visible_desc_id)


def _parse_tech_description(
    text_map: dict[str, str] | None, tech: ET.Element | None
) -> str | None:

    if text_map is None or tech is None:
        return None

    tech_desc_id = _text_of(tech.find("TechDescription"))

    if not tech_desc_id:
        return None

    return text_map.get(tech_desc_id)


def parse_texts_xml(texts_xml_path: str | Path) -> dict[str, str]:
    """Reads localization texts from an XML file (e.g., texts_english.xml).

    Expects a format like:
    <Text>
      <LineId>-6905994092355621225</LineId>
      <Text>Healthy Competition</Text>
    </Text>
    """

    texts_xml_path = Path(texts_xml_path)

    if not texts_xml_path.exists():
        return {}

    try:
        tree = ET.parse(str(texts_xml_path))
        root = tree.getroot()

    except Exception:
        return {}

    text_map: dict[str, str] = {}

    for entry in root.findall(".//Text"):
        line_id = _text_of(entry.find("LineId"))
        content = _text_of(entry.find("Text"))

        if line_id and content:
            text_map[line_id] = content

    return text_map


def parse_assets_xml_assets_tech_nodes(
    assets_xml_path: str | Path,
    text_map: dict[str, str] | None = None,
    category_offsets: dict[str, list[float]] | None = None,
) -> tuple[list[TechNode], list[str]]:
    """Reads all tech assets from assets.xml.

    A tech node is identified via:
      <Asset><Template>Tech</Template>...</Asset>

    Technical fields used for display:
      - GUID / Name
      - IsRepeatable
      - KnowledgeNeeded / RepeatableCostFactor
      - GridPosition (X/Y)
      - Color
    """

    assets_xml_path = Path(assets_xml_path)

    if not assets_xml_path.exists():
        raise FileNotFoundError(str(assets_xml_path))

    tree = ET.parse(str(assets_xml_path))
    root = tree.getroot()

    if category_offsets is None:
        category_offsets = {}

    tech_offsets_map: dict[str, tuple[float, float]] = {}
    tech_stagger_map: dict[str, int] = {}
    guid_to_category: dict[str, str] = {}
    pooled_tech_guids: set[str] = set()

    found_categories: set[str] = set()


    for asset in root.iter("Asset"):
        template = _text_of(asset.find("Template"))

        if template == "Trigger":
            # Suche nach ActionUnlockAsset -> UnhideAssets (GatePools)
            for action in asset.findall("Values/Trigger/TriggerActions/Item/TriggerAction"):

                if _text_of(action.find("Template")) == "ActionUnlockAsset":
                    for unhide_item in action.findall("Values/ActionUnlockAsset/UnhideAssets/Item"):
                        u_guid = _text_of(unhide_item.find("Asset"))

                        if u_guid:
                            pooled_tech_guids.add(u_guid)

            continue

        if template != "TechCategory":
            continue

        # Sammle alle Techs, die in einer Kategorie gelistet sind
        for item in asset.findall("Values/TechCategory/Techs/Item"):
            t_guid = _text_of(item.find("Tech"))

            if t_guid:
                pooled_tech_guids.add(t_guid)

        cat_name = (_text_of(asset.find("Values/Standard/Name")) or "").replace("CategoryConfig ", "")

        found_categories.add(cat_name)

        # Get offsets from config
        off = category_offsets.get(cat_name, [0.0, 0.0, 0.0])
        off_x = float(off[0])
        off_y = float(off[1])
        stagger_type = int(off[2]) if len(off) > 2 else 0

        for item in asset.findall("Values/TechCategory/Techs/Item"):
            t_guid = _text_of(item.find("Tech"))

            if t_guid:
                tech_offsets_map[t_guid] = (off_x, off_y)
                tech_stagger_map[t_guid] = stagger_type
                guid_to_category[t_guid] = cat_name

    nodes: list[TechNode] = []

    for asset in root.iter("Asset"):
        template = _text_of(asset.find("Template"))
        if template != "Tech":
            continue

        # Standard values extraction
        std = asset.find("Values/Standard")
        tech = asset.find("Values/Tech")
        guid = _text_of(std.find("GUID") if std is not None else None)
        name = _text_of(std.find("Name") if std is not None else None)

        if guid is None:
            # Incomplete record: skip
            continue

        if name is None:
            name = guid

        if guid not in pooled_tech_guids:
            continue

        is_repeatable_text = _text_of(tech.find("IsRepeatable") if tech is not None else None)
        is_repeatable = is_repeatable_text == "1"
        is_gate_text = _text_of(tech.find("IsGate") if tech is not None else None)
        is_gate = is_gate_text == "1"
        knowledge_needed = _parse_int(_text_of(tech.find("KnowledgeNeeded") if tech is not None else None))
        repeatable_cost_factor = _parse_float(
            _text_of(tech.find("RepeatableCostFactor") if tech is not None else None)
        )

        # Parse original grid positions
        raw_grid_x = _parse_int(_text_of(tech.find("GridPosition/X") if tech is not None else None))
        raw_grid_y = _parse_int(_text_of(tech.find("GridPosition/Y") if tech is not None else None))

        # Defaults to 0 if X or Y is missing
        raw_grid_x = raw_grid_x if raw_grid_x is not None else 0
        raw_grid_y = raw_grid_y if raw_grid_y is not None else 0

        # Apply offsets for grid display
        off_x, off_y = tech_offsets_map.get(guid, (0.0, 0.0))
        grid_x = raw_grid_x + off_x
        grid_y = raw_grid_y + off_y

        # Apply staggering based on configuration
        stagger_type = tech_stagger_map.get(guid, 0)

        if stagger_type == 1: # Odd Columns (e.g. 1st, 3rd...)
            if raw_grid_x % 2 != 0:
                grid_y += 0.5

        elif stagger_type == 2: # Even Columns (e.g. 2nd, 4th...)
            if raw_grid_x % 2 == 0:
                grid_y += 0.5

        elif stagger_type == 3: # Civic Special
            if raw_grid_x == 0:
                grid_y -= 0.5
            # even negative x gets y+0.5
            elif (raw_grid_x < 0) and (raw_grid_x % 2 == 0):
                grid_y += 0.5
            # even positive x gets y-0.5
            elif (raw_grid_x > 0) and (raw_grid_x % 2 == 0):
                grid_y -= 0.5

        color = _text_of(tech.find("Color") if tech is not None else None)
        color = color if color is not None else "Unknown"

        visible_name_id = _text_of(tech.find("VisibleTechName") if tech is not None else None)
        display_name = name

        if text_map and visible_name_id and visible_name_id in text_map:
            display_name = text_map[visible_name_id]

        unlock_reward_guid = _text_of(tech.find("Rewards/Unlocks/Item/UnlockReward") if tech is not None else None)
        effect_asset_guid = _text_of(tech.find("Rewards/Effects/Item/EffectAsset") if tech is not None else None)

        unlock_trigger_guids: list[str] = []

        if tech is not None:
            # Specifically look for TechResearchableTrigger as a direct child of <Tech>
            trigger_elem = tech.find("TechResearchableTrigger")

            if trigger_elem is not None:
                ut_guid = _text_of(trigger_elem)

                if ut_guid and ut_guid != "0":
                    unlock_trigger_guids.append(ut_guid)

        nodes.append(
            TechNode(
                guid=guid,
                name=display_name,
                description=_parse_description(text_map=text_map, tech=tech),
                tech_description=_parse_tech_description(text_map=text_map, tech=tech),
                is_repeatable=is_repeatable,
                is_gate=is_gate,
                knowledge_needed=knowledge_needed,
                repeatable_cost_factor=repeatable_cost_factor,
                grid_x=grid_x,
                raw_grid_x=raw_grid_x,
                grid_y=grid_y,
                raw_grid_y=raw_grid_y,
                color=color,
                unlock_trigger_guids=tuple(unlock_trigger_guids),
                unlock_reward_guid=unlock_reward_guid,
                effect_asset_guid=effect_asset_guid,
            )
        )


    return nodes, sorted(list(found_categories))



################################################################################
# TRIGGER PARSING
################################################################################


def _element_to_pretty_xml_snippet(elem: ET.Element) -> str:

    e2 = copy.deepcopy(elem)

    # Entferne vorhandene Leerräume (Whitespace), damit indent() komplett neu formatieren kann
    for node in e2.iter():
        if node.text is not None and not node.text.strip():
            node.text = None
        if node.tail is not None and not node.tail.strip():
            node.tail = None

    ET.indent(e2, space="  ")


    return ET.tostring(e2, encoding="unicode")


def parse_assets_xml_asset_values(
    assets_xml_path: str | Path,
) -> dict[str, str]:
    """Index assets by GUID -> pretty-printed XML of their <Values> block.

    Returns:
      guid -> pretty-printed XML snippet (string) of the <Values> subtree.
    """

    assets_xml_path = Path(assets_xml_path)

    if not assets_xml_path.exists():
        raise FileNotFoundError(str(assets_xml_path))

    tree = ET.parse(str(assets_xml_path))
    root = tree.getroot()

    asset_values_by_guid: dict[str, str] = {}

    for asset in root.iter("Asset"):
        std = asset.find("Values/Standard")
        guid = _text_of(std.find("GUID") if std is not None else None)

        if not guid:
            continue

        values_elem = asset.find("Values")

        if values_elem is not None:
            asset_values_by_guid[guid] = _element_to_pretty_xml_snippet(values_elem)

    return asset_values_by_guid



################################################################################
# RENDERING
################################################################################


def color_to_qcolor(color_name: str) -> QColor:

    normalized = color_name.strip().lower()
    mapping: dict[str, QColor] = {
        "green": QColor(60, 160, 90),
        "blue": QColor(60, 110, 205),
        "brown": QColor(150, 100, 60),
        "red": QColor(200, 70, 70),
        "purple": QColor(150, 90, 190),
        "yellow": QColor(210, 190, 60),
        "black": QColor(35, 35, 35),
        "white": QColor(235, 235, 235),
        "orange": QColor(220, 140, 60),
        "gray": QColor(140, 140, 140),
        "grey": QColor(140, 140, 140),
        "rustred": QColor(140, 0, 0),
    }


    return mapping.get(normalized, QColor(140, 140, 140))


def clamp(v: int, lo: int, hi: int) -> int:

    if v < lo:
        return lo

    if v > hi:
        return hi

    return v


class XmlHighlighter(QSyntaxHighlighter):
    """Simple syntax highlighter for XML data."""

    def __init__(self, parent: t.Any):

        super().__init__(parent)

        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        # Tag rule: <...>
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#569cd6"))  # Blue
        self._rules.append((QRegularExpression(r"<[^>]+>"), tag_format))

        # Comment rule: <!-- ... -->
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))  # Green
        self._rules.append((QRegularExpression(r"<!--.*?-->"), comment_format))

    def highlightBlock(self, text: str):

        for pattern, char_format in self._rules:
            match_iterator = pattern.globalMatch(text)

            while match_iterator.hasNext():
                match = match_iterator.next()

                self.setFormat(
                    match.capturedStart(),
                    match.capturedLength(),
                    char_format
                )

        return


class ClickableTechRectItem(QGraphicsRectItem):
    """QGraphicsRectItem that triggers a callback on click."""

    def __init__(
        self,
        node: TechNode,
        on_selected: t.Callable[[TechNode], None],
        parent: QGraphicsRectItem | None = None,
    ):

        super().__init__(parent)

        self._node = node
        self._on_selected = on_selected
        self._base_brush: QColor | None = None
        self._base_pen = None
        self._hovered = False
        self._selected = False
        self._label: QGraphicsTextItem | None = None

        self.setToolTip(node.name)
        self.setAcceptHoverEvents(True)


    def set_visuals(self, brush: QColor, pen) -> None:

        self._base_brush = brush
        self._base_pen = pen

        self.setBrush(self._base_brush)

        if self._base_pen is not None:
            self.setPen(self._base_pen)

        return


    def set_label(self, label: QGraphicsTextItem) -> None:

        self._label = label

        return


    def set_selected(self, selected: bool) -> None:

        self._selected = selected

        if self._base_brush is None:
            return

        if self._selected:
            self.setBrush(Qt.GlobalColor.white)

            if self._label:
                self._label.setDefaultTextColor(Qt.GlobalColor.black)

            if self._base_pen is not None:
                self.setPen(self._base_pen)
                self.pen().setWidthF(max(1.0, self.pen().widthF()))

        else:
            if self._hovered:
                self.setBrush(self._base_brush.lighter(130))

            else:
                self.setBrush(self._base_brush)

            if self._label:
                self._label.setDefaultTextColor(QColor(240, 240, 240))

            if self._base_pen is not None:
                self.setPen(self._base_pen)

        return


    def hoverEnterEvent(self, event):  # noqa: N802

        self._hovered = True

        if not self._selected and self._base_brush is not None:
            self.setBrush(self._base_brush.lighter(130))

        event.accept()

    def hoverLeaveEvent(self, event):  # noqa: N802

        self._hovered = False

        if not self._selected and self._base_brush is not None:
            self.setBrush(self._base_brush)

        event.accept()

    def mousePressEvent(self, event):  # noqa: N802

        if callable(self._on_selected):
            self._on_selected(self._node)

        event.accept()


class TechTreeView(QGraphicsView):
    """Displays TechNodes as grid boxes."""

    def __init__(self, parent: QWidget | None = None):

        super().__init__(parent)

        bg_path = get_resource_path("techbg.jpg")
        if bg_path.exists():
            self.setBackgroundBrush(QBrush(QPixmap(str(bg_path))))

        else:
            self.setBackgroundBrush(QColor("#CBAB94"))

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._cell_w = 50
        self._cell_h = 45
        self._gap = 5
        self._max_visible_label_chars = 12
        self._on_node_selected: t.Callable[[TechNode], None] | None = None
        self._selected_guid: str | None = None
        self._last_pan_pos: QPointF | None = None
        self._panning_active: bool = False
        self._rect_by_guid: dict[str, ClickableTechRectItem] = {}


    def set_on_node_selected(self, on_node_selected: t.Callable[[TechNode], None]) -> None:

        self._on_node_selected = on_node_selected


    def clear_scene(self) -> None:

        self._scene.clear()
        self._selected_guid = None
        self._rect_by_guid.clear()

        return


    def mousePressEvent(self, event):  # noqa: N802

        if event.button() == Qt.MouseButton.RightButton:
            self._panning_active = True
            self._last_pan_pos = event.pos()
            event.accept()

        else:
            super().mousePressEvent(event)


    def mouseMoveEvent(self, event):  # noqa: N802

        if self._panning_active and self._last_pan_pos is not None:
            delta = event.pos() - self._last_pan_pos

            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())

            self._last_pan_pos = event.pos()
            event.accept()

        else:
            super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event):  # noqa: N802

        if event.button() == Qt.MouseButton.RightButton:
            self._panning_active = False
            self._last_pan_pos = None
            event.accept()

        else:
            super().mouseReleaseEvent(event)


    def wheelEvent(self, event):  # noqa: N802

        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        # Anchor zoom at the mouse position
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor

        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)


    def populate(self, nodes: list[TechNode]) -> None:

        self.clear_scene()

        if not nodes:
            return

        # Stabilisierung: Wir nutzen die kleinsten Werte im Baum als festen Anker
        # grid_margin sorgt für den Abstand zum Rand (deine "Dummy-Zelle")
        grid_margin = 4

        all_grid_x = [n.grid_x for n in nodes]
        all_grid_y = [n.grid_y for n in nodes]
        
        min_x = math.floor(min(all_grid_x)) - grid_margin
        max_x = math.ceil(max(all_grid_x)) + grid_margin
        min_y = math.floor(min(all_grid_y)) - grid_margin
        max_y = math.ceil(max(all_grid_y)) + grid_margin

        for node in nodes:

            x = (node.grid_x - min_x) * (self._cell_w + self._gap)
            y = (node.grid_y - min_y) * (self._cell_h + self._gap)

            base_color = color_to_qcolor(node.color)
            rect = ClickableTechRectItem(
                node=node,
                on_selected=self._handle_node_selected,
            )
            rect.setRect(0, 0, self._cell_w, self._cell_h)
            rect.setPos(x, y)
            self._rect_by_guid[node.guid] = rect

            if node.is_gate:
                pen = QPen(QColor(255, 0, 0))
                pen.setWidthF(4)

                rect.set_visuals(base_color, pen)
                pen_w = pen.widthF()
                inset = max(0.0, (pen_w / 2.0) - 0.5)
                new_w = max(1.0, self._cell_w - 2.0 * inset)
                new_h = max(1.0, self._cell_h - 2.0 * inset)
                rect.setRect(inset, inset, new_w, new_h)

            else:
                rect.set_visuals(base_color, QPen(base_color.darker(150)))

            rect.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
            self._scene.addItem(rect)

            label = QGraphicsTextItem(rect)
            rect.set_label(label)
            label.setDefaultTextColor(QColor(240, 240, 240))
            short_name = node.name

            if len(short_name) > self._max_visible_label_chars:
                short_name = short_name[: self._max_visible_label_chars - 3] + "..."

            label.setPlainText(short_name)
            label.setFont(QFont("Segoe UI", 8))
            label.setTextWidth(self._cell_w)
            label.setPos(2, 2)

            if node.unlock_trigger_guids:
                dot_size = 10
                dot = QGraphicsEllipseItem(
                    self._cell_w - dot_size - 4,
                    4,
                    dot_size,
                    dot_size,
                    rect
                )
                dot.setBrush(QColor(255, 165, 0))
                dot.setPen(QPen(Qt.GlobalColor.black, 1))
                dot.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        padding = 40
        left = 0
        top = 0
        width = (max_x - min_x + 1) * (self._cell_w + self._gap) + self._cell_w + padding
        height = (max_y - min_y + 1) * (self._cell_h + self._gap) + self._cell_h + padding

        self.setSceneRect(left, top, width, height)

        # Center on logical grid 0,0
        cx = (0 - min_x) * (self._cell_w + self._gap) + self._cell_w / 2
        cy = (0 - min_y) * (self._cell_h + self._gap) + self._cell_h / 2
        self.centerOn(cx, cy)

        return


    def _handle_node_selected(self, node: TechNode) -> None:

        for guid, rect in self._rect_by_guid.items():
            rect.set_selected(guid == node.guid)

        self._selected_guid = node.guid

        if self._on_node_selected is not None:
            self._on_node_selected(node)

        return




################################################################################
# MAIN WINDOW
################################################################################


class OptionsDialog(QDialog):
    """Dialog for application settings."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None):

        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Options")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Path Selection
        path_group = QHBoxLayout()
        self._path_edit = QLineEdit(self._config.xml_root_path)
        self._path_edit.setPlaceholderText("Select root folder for XML files...")
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._on_browse_clicked)

        path_group.addWidget(self._path_edit)
        path_group.addWidget(browse_btn)

        # Category Offsets Table
        layout.addWidget(QLabel("<b>Category Offsets:</b>"))
        self._offset_table = QTableWidget()
        self._offset_table.setColumnCount(4)
        self._offset_table.setHorizontalHeaderLabels(["Category", "Offset X", "Offset Y", "Staggering"])
        self._offset_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Populate table from config
        categories = sorted(self._config.category_offsets.keys())
        self._offset_table.setRowCount(len(categories))

        for i, cat in enumerate(categories):
            off = self._config.category_offsets[cat]
            stagger_type = int(off[2]) if len(off) > 2 else 0

            cat_item = QTableWidgetItem(cat)
            cat_item.setFlags(cat_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            self._offset_table.setItem(i, 0, cat_item)
            self._offset_table.setItem(i, 1, QTableWidgetItem(str(off[0])))
            self._offset_table.setItem(i, 2, QTableWidgetItem(str(off[1])))

            combo = QComboBox()
            combo.addItems(["None", "Odd (1st)", "Even (2nd)", "Civic Spec"])
            combo.setCurrentIndex(stagger_type)
            self._offset_table.setCellWidget(i, 3, combo)

        layout.addWidget(self._offset_table)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save_clicked)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch(1)
        btn_layout.addWidget(save_btn)

        btn_layout.addWidget(cancel_btn)

        layout.addWidget(QLabel("<b>XML Root Directory:</b>"))
        layout.addLayout(path_group)
        layout.addStretch(1)
        layout.addLayout(btn_layout)

    def _on_browse_clicked(self) -> None:

        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "Select XML Root Directory", 
            self._path_edit.text() or str(Path.cwd())
        )

        if dir_path:
            self._path_edit.setText(dir_path)

    def _on_save_clicked(self) -> None:

        self._config.xml_root_path = self._path_edit.text()

        # Update offsets from table
        new_offsets = {}
        for i in range(self._offset_table.rowCount()):
            cat = self._offset_table.item(i, 0).text()
            try:
                x = float(self._offset_table.item(i, 1).text())
                y = float(self._offset_table.item(i, 2).text())

                combo = self._offset_table.cellWidget(i, 3)
                stagger_type = combo.currentIndex()
                new_offsets[cat] = [x, y, float(stagger_type)]

            except ValueError:
                # Keep old value if invalid input
                new_offsets[cat] = self._config.category_offsets.get(cat, [0.0, 0.0, 0.0])

        self._config.category_offsets = new_offsets

        self._config.save()
        self.accept()



################################################################################
# MAIN WINDOW COMPONENTS
################################################################################


class DetailsPanel(QWidget):
    """Right panel for tech details."""

    def __init__(self, parent: QWidget | None = None):

        super().__init__(parent)

        root_layout = QVBoxLayout(self)

        # Header
        self._title = QLabel("<b>Details</b>")
        self._title.setWordWrap(True)
        self._title.setFont(QFont("Segoe UI", 12))

        # Value Labels
        self._guid_value = QLabel("-")
        self._description_value = QLabel("-")
        self._description_value.setWordWrap(True)
        self._tech_description_value = QLabel("-")
        self._tech_description_value.setWordWrap(True)
        self._knowledge_needed_value = QLabel("-")
        self._repeat_value = QLabel("-")
        self._is_repeatable_value = QLabel("-")
        self._is_gate_value = QLabel("-")
        self._unlock_reward_value = QLabel("-")
        self._effect_asset_value = QLabel("-")
        self._color_value = QLabel("-")
        self._grid_value = QLabel("-")
        self._unlock_trigger_value = QLabel("-")
        self._unlock_trigger_value.setWordWrap(True)

        self._buffs_value = QLabel("-")
        self._buffs_value.setWordWrap(True)
        self._current_guid_xml: str = "-"
        self._current_trigger_xml: str = "-"
        self._current_reward_xml: str = "-"
        self._current_effect_xml: str = "-"
        self._current_buffs_xml: str = "-"

        self._xml_highlighter: XmlHighlighter | None = None

        # Helper to make all labels in the panel selectable
        for widget in [
            self._title, self._guid_value, self._description_value,
            self._tech_description_value, self._knowledge_needed_value,
            self._repeat_value, self._is_repeatable_value, self._is_gate_value,
            self._unlock_reward_value, self._effect_asset_value, self._color_value,
            self._buffs_value,
            self._grid_value, self._unlock_trigger_value
        ]:
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        def _add_labeled_widget(label_text: str, widget: QWidget):
            header = QLabel(f"<b>{label_text}</b>")
            header.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            root_layout.addWidget(header)
            root_layout.addWidget(widget)

        root_layout.addWidget(self._title)

        def _add_details_section(label_text: str, value_label: QLabel, callback):

            header_layout = QHBoxLayout()
            header_label = QLabel(f"<b>{label_text}</b>")
            header_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            btn = QPushButton("Details")
            btn.setFixedWidth(80)
            btn.setEnabled(False)
            btn.clicked.connect(callback)

            header_layout.addWidget(header_label)
            header_layout.addWidget(btn)
            header_layout.addStretch(1)

            root_layout.addLayout(header_layout)
            root_layout.addWidget(value_label)

            return btn

        self._guid_details_button = _add_details_section("GUID:", self._guid_value, self._on_guid_details_clicked)
        _add_labeled_widget("Description:", self._description_value)
        _add_labeled_widget("Tech Description:", self._tech_description_value)
        _add_labeled_widget("KnowledgeNeeded:", self._knowledge_needed_value)
        _add_labeled_widget("Repeatfactor:", self._repeat_value)
        _add_labeled_widget("IsRepeatable:", self._is_repeatable_value)
        _add_labeled_widget("IsGate:", self._is_gate_value)

        self._reward_details_button = _add_details_section("UnlockReward:", self._unlock_reward_value, self._on_reward_details_clicked)
        self._effect_details_button = _add_details_section("EffectAsset:", self._effect_asset_value, self._on_effect_details_clicked)
        self._buffs_details_button = _add_details_section("Buffs:", self._buffs_value, self._on_buffs_details_clicked)

        _add_labeled_widget("Color:", self._color_value)
        _add_labeled_widget("GridPosition:", self._grid_value)

        self._trigger_details_button = _add_details_section("UnlockTrigger(s):", self._unlock_trigger_value, self._on_trigger_details_clicked)

        root_layout.addStretch(1)

        return


    def _on_guid_details_clicked(self) -> None:

        self._show_xml_dialog("Asset XML Details", self._current_guid_xml)

        return


    def _on_trigger_details_clicked(self) -> None:

        self._show_xml_dialog("Trigger XML Details", self._current_trigger_xml)

        return


    def _on_reward_details_clicked(self) -> None:

        self._show_xml_dialog("Reward XML Details", self._current_reward_xml)

        return


    def _on_effect_details_clicked(self) -> None:

        self._show_xml_dialog("Effect XML Details", self._current_effect_xml)

        return


    def _on_buffs_details_clicked(self) -> None:

        self._show_xml_dialog("Buff XML Details", self._current_buffs_xml)

        return


    def _show_xml_dialog(self, title: str, content: str) -> None:

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(800, 600)

        layout = QVBoxLayout(dialog)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(content)
        text_edit.setFont(QFont("Consolas", 10))
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Syntax Highlighting and Dark Theme for code
        text_edit.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        self._xml_highlighter = XmlHighlighter(text_edit.document())

        layout.addWidget(text_edit)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

        return


    def show_node_details(self, node: TechNode, asset_values_by_guid: dict[str, str] | None = None) -> None:

        self._title.setText(node.name)


        # GUID Section
        self._guid_value.setText(node.guid)
        self._current_guid_xml = "-"

        self._guid_details_button.setEnabled(True)

        if asset_values_by_guid:
            self._current_guid_xml = asset_values_by_guid.get(node.guid, f"<!-- Asset {node.guid} not found -->")

        else:
            self._current_guid_xml = "Asset values not loaded."


        if node.description:
            self._description_value.setText(node.description)

        else:
            self._description_value.setText("-")

        if node.tech_description:
            self._tech_description_value.setText(node.tech_description)

        else:
            self._tech_description_value.setText("-")

        if node.knowledge_needed is not None:
            self._knowledge_needed_value.setText(f"{node.knowledge_needed:,}")

        else:
            self._knowledge_needed_value.setText("-")

        if node.is_repeatable:
            if node.repeatable_cost_factor is not None:
                self._repeat_value.setText(f"{node.repeatable_cost_factor:g}")

            else:
                self._repeat_value.setText("Repeat")

        else:
            self._repeat_value.setText("-")

        self._is_repeatable_value.setText("Yes" if node.is_repeatable else "No")
        self._is_gate_value.setText("Yes" if node.is_gate else "No")


        # Reward Section
        self._unlock_reward_value.setText(node.unlock_reward_guid if node.unlock_reward_guid else "-")
        self._current_reward_xml = "-"

        self._reward_details_button.setEnabled(False)

        if node.unlock_reward_guid:
            self._reward_details_button.setEnabled(True)

            if asset_values_by_guid:
                self._current_reward_xml = asset_values_by_guid.get(node.unlock_reward_guid, f"<!-- Asset {node.unlock_reward_guid} not found -->")

            else:
                self._current_reward_xml = "Asset values not loaded."


        # Effect Section
        self._effect_asset_value.setText(node.effect_asset_guid if node.effect_asset_guid else "-")
        self._current_effect_xml = "-"

        self._effect_details_button.setEnabled(False)

        if node.effect_asset_guid:
            self._effect_details_button.setEnabled(True)

            if asset_values_by_guid:
                self._current_effect_xml = asset_values_by_guid.get(node.effect_asset_guid, f"<!-- Asset {node.effect_asset_guid} not found -->")

            else:
                self._current_effect_xml = "Asset values not loaded."


        # Buffs Section (derived from EffectAsset)
        self._buffs_value.setText("-")
        self._current_buffs_xml = "-"

        self._buffs_details_button.setEnabled(False)

        buff_guids: list[str] = []

        if node.effect_asset_guid and asset_values_by_guid:
            effect_xml = asset_values_by_guid.get(node.effect_asset_guid)

            if effect_xml:
                try:
                    # Parsen des Snippets, um Buffs zu finden
                    root_effect = ET.fromstring(effect_xml)
                    for item in root_effect.findall(".//Buffs/Item"):
                        b_guid = _text_of(item.find("GUID"))

                        if b_guid:
                            buff_guids.append(b_guid)

                except Exception:
                    pass

        if buff_guids:
            self._buffs_value.setText(", ".join(buff_guids))
            self._buffs_details_button.setEnabled(True)

            if asset_values_by_guid:
                xml_snippets: list[str] = []

                for b_guid in buff_guids:
                    b_xml = asset_values_by_guid.get(b_guid)

                    if b_xml:
                        xml_snippets.append(b_xml)

                    else:
                        xml_snippets.append(f"<!-- Buff Asset {b_guid} not found -->")

                self._current_buffs_xml = "\n\n".join(xml_snippets)


        self._color_value.setText(node.color)
        self._grid_value.setText(f"X={node.raw_grid_x}, Y={node.raw_grid_y}")


        # Trigger Section
        if not node.unlock_trigger_guids:
            self._unlock_trigger_value.setText("-")
            self._current_trigger_xml = "-"
            self._trigger_details_button.setEnabled(False)

            return

        self._unlock_trigger_value.setText(", ".join(node.unlock_trigger_guids))
        self._trigger_details_button.setEnabled(True)

        if not asset_values_by_guid:
            self._current_trigger_xml = "Trigger values not loaded."

            return

        xml_snippets: list[str] = []

        for guid in node.unlock_trigger_guids:
            xml = asset_values_by_guid.get(guid)

            if xml:
                #xml_snippets.append(f"<!-- Trigger GUID {guid} -->\n{xml}")
                xml_snippets.append(f"{xml}")

            else:
                #xml_snippets.append(f"<!-- Trigger GUID {guid} not found in assets.xml -->")
                xml_snippets.append(f"")

        self._current_trigger_xml = "\n\n".join(xml_snippets)

        return


class TechTreeWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #CBAB94;
                color: #000000;
            }
            QScrollArea, QGraphicsView {
                border: 1px solid #8C6F61;
                background-color: #CBAB94;
            }
            QPushButton {
                background-color: #5F022E;
                color: #FFFFFF;
                border-radius: 2px;
                padding: 4px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #82033F;
            }
            QPushButton:disabled {
                background-color: #8C6F61;
                color: #A0A0A0;
            }
            QComboBox {
                background-color: #5F022E;
                color: #FFFFFF;
                border: 1px solid #5F022E;
                border-radius: 2px;
                padding: 4px 12px;
                font-weight: bold;
            }
            QComboBox:hover {
                background-color: #82033F;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 1px;
                border-left-color: #8C6F61;
                border-left-style: solid;
                border-top-right-radius: 2px;
                border-bottom-right-radius: 2px;
            }
            QComboBox QAbstractItemView {
                background-color: #CBAB94;
                color: #000000;
                selection-background-color: #82033F;
                selection-color: #FFFFFF;
            }
        """)

        # Core components
        self._view = TechTreeView(self)
        self._details = DetailsPanel(self)

        self._details_scroll = QScrollArea()
        self._details_scroll.setWidget(self._details)
        self._details_scroll.setWidgetResizable(True)

        self._details_scroll.setFixedWidth(300)

        self._asset_values_by_guid: dict[str, str] = {}
        self._available_languages: dict[str, Path] = {}
        self._config = AppConfig()
        self._config.load()

        self._view.set_on_node_selected(self._show_node_details)

        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

        # Toolbar setup
        self._reload_button = QPushButton("Reload", self)
        self._reload_button.clicked.connect(self._on_reload_clicked)

        self._options_button = QPushButton("Options", self)
        self._options_button.clicked.connect(self._on_options_clicked)

        self._language_dropdown = QComboBox(self)
        self._language_dropdown.currentIndexChanged.connect(self._on_reload_clicked)

        # Kofi integration
        self._kofi_button = QPushButton(self)
        self._kofi_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kofi_button.setFixedWidth(100)  # Kontrolliert die Breite des Buttons
        self._kofi_button.setFixedHeight(30)  # Kontrolliert die Höhe des Buttons
        self._kofi_button.setIconSize(QSize(100, 40))  # Kontrolliert die Größe der Grafik im Button
        self._kofi_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://ko-fi.com/gz2k2")))
        kofi_path = get_resource_path("kofi5.webp")

        if kofi_path.exists():
            self._kofi_button.setIcon(QIcon(str(kofi_path)))

        self._hint_label = QLabel(
            "Mousewheel to zoom, right-click and drag to pan. Click nodes for details. Red Borders = Gates, Orange Dot = Locked by Default.",
            self,
        )
        self._hint_label.setWordWrap(True)

        # Layout assembly
        toolbar = QHBoxLayout()
        toolbar.addWidget(self._reload_button)
        toolbar.addWidget(QLabel("Language:"))
        toolbar.addWidget(self._language_dropdown)
        toolbar.addStretch(1)

        toolbar.addWidget(self._options_button)
        toolbar.addWidget(self._kofi_button)

        root = QWidget(self)
        layout = QVBoxLayout(root)

        layout.addWidget(self._hint_label)
        layout.addLayout(toolbar)
        content_layout = QHBoxLayout()
        content_layout.addWidget(self._view, 1)
        content_layout.addWidget(self._details_scroll, 0)

        layout.addLayout(content_layout, 1)

        self.setCentralWidget(root)

        self._assets_xml_path: Path | None = None

        self._initialize_data()

        return


    def _initialize_data(self) -> None:
        """Attempts to load data from config."""

        if self._config.xml_root_path:
            found = self._try_find_assets_from_config()
            
            if found:
                self._update_language_list()
                self._load_and_render()

        return


    def _try_find_assets_from_config(self) -> bool:
        """Searches for assets.xml based on config settings."""

        root = Path(self._config.xml_root_path)

        if not root.exists():
            return False

        pattern = "**/assets.xml"
        
        try:
            for p in root.glob(pattern):
                self._assets_xml_path = p
                return True
                
        except Exception:
            pass

        return False


    def _on_options_clicked(self) -> None:

        dlg = OptionsDialog(self._config, self)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            # After saving new options, try to reload automatically
            found = self._try_find_assets_from_config()
            
            if found:
                self._update_language_list()
                self._load_and_render()
            
            else:
                QMessageBox.warning(
                    self, "Not Found", 
                    "Could not find assets.xml in the specified directory."
                )

        return


    def _update_language_list(self) -> None:
        """Scans folder for texts_*.xml and populates the dropdown."""

        if not self._config.xml_root_path:
            return

        self._available_languages.clear()
        self._language_dropdown.blockSignals(True)
        self._language_dropdown.clear()


        root = Path(self._config.xml_root_path)
        if not root.exists():
            return

        try:
            for xml_file in root.glob("**/texts_*.xml"):
                # Example: texts_english.xml -> name 'english'
                lang_name = xml_file.stem.replace("texts_", "")
                self._available_languages[lang_name] = xml_file
                self._language_dropdown.addItem(lang_name)
        except Exception:
            # Ignore errors during globbing, e.g., permission issues
            pass


        # Try to default to english or the first available
        if "english" in self._available_languages:
            idx = self._language_dropdown.findText("english")
            self._language_dropdown.setCurrentIndex(idx)

        elif self._language_dropdown.count() > 0:
            self._language_dropdown.setCurrentIndex(0)

        self._language_dropdown.blockSignals(False)

        return


    def _on_reload_clicked(self) -> None:

        if self._assets_xml_path is None:
            QMessageBox.information(self, "Info", "Please open assets.xml first.")

            return

        self._load_and_render()

        return


    def _show_node_details(self, node: TechNode) -> None:

        self._details.show_node_details(node, asset_values_by_guid=self._asset_values_by_guid)

        return


    def _load_and_render(self) -> None:

        if self._assets_xml_path is None:
            return

        try:
            self._status.showMessage(f"Loading: {self._assets_xml_path} ...")

            text_map = {}
            lang = self._language_dropdown.currentText()

            if lang in self._available_languages:
                text_map = parse_texts_xml(self._available_languages[lang])

            nodes, found_categories = parse_assets_xml_assets_tech_nodes(
                self._assets_xml_path, text_map, self._config.category_offsets
            )

            # Sync categories to config
            config_changed = False
            for cat in found_categories:
                if cat not in self._config.category_offsets:
                    self._config.category_offsets[cat] = [0.0, 0.0, 0.0]
                    config_changed = True

            if config_changed:
                self._config.save()

            self._asset_values_by_guid = parse_assets_xml_asset_values(self._assets_xml_path)

            self._view.populate(nodes)

            self._status.showMessage(
                f"Loaded {len(nodes)} tech nodes"
            )

        except Exception as exc:  # noqa: BLE001
            self._status.showMessage("Error")
            QMessageBox.critical(self, "Error", f"Could not load assets.xml:\n{exc}")

        return



################################################################################
# ENTRY POINT
################################################################################


def main() -> int:

    app = QApplication(sys.argv)
    window = TechTreeWindow()

    window.show()

    return app.exec()


if __name__ == "__main__":

    raise SystemExit(main())
