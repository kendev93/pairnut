"""Primary application UI."""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from ..database import repositories
from ..domain.models import DefectLevel, SerialMode
from ..services.matching import get_candidates_for_variety
from ..services.serials import next_serial_no
from .components import labeled_metric, section_title, status_text


@dataclass
class FormState:
    editing_variety_id: int | None = None
    editing_walnut_id: int | None = None


class PairNutUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_view = "varieties"
        self.selected_variety_id: int | None = None
        self.status_message = "准备就绪"
        self.form_state = FormState()

    def render(self) -> None:
        self.page.clean()
        self.page.add(
            ft.Container(
                content=ft.Column(
                    controls=[
                        self._build_header(),
                        self._build_brand_banner(),
                        self._build_navigation(),
                        ft.Divider(),
                        self._build_view(),
                    ],
                    spacing=16,
                    expand=True,
                ),
                padding=20,
                expand=True,
            )
        )
        self.page.update()

    def _build_header(self) -> ft.Row:
        return ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("PairNut", size=28, weight=ft.FontWeight.BOLD),
                        ft.Text("本地核桃配对工具 V1", color=ft.Colors.BLUE_GREY_400),
                    ],
                    spacing=4,
                    expand=True,
                ),
                status_text(self.status_message),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _build_brand_banner(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Image(
                            src="cover.png",
                            height=210,
                            fit=ft.BoxFit.CONTAIN,
                            border_radius=16,
                        ),
                        bgcolor=ft.Colors.WHITE,
                        padding=16,
                        border_radius=20,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("文玩核桃智能配对工具", size=26, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "先按品种建规则，再录入核桃数据，用三维偏差、克重接近度和瑕疵扣分生成候选配对。",
                                size=15,
                                color=ft.Colors.BLUE_GREY_600,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Chip(label=ft.Text("同品种内配对"), bgcolor=ft.Colors.BROWN_50),
                                    ft.Chip(label=ft.Text("瑕疵参与扣分"), bgcolor=ft.Colors.AMBER_50),
                                    ft.Chip(label=ft.Text("候选可锁定/拉黑"), bgcolor=ft.Colors.BLUE_50),
                                ],
                                wrap=True,
                                spacing=10,
                            ),
                        ],
                        spacing=14,
                        expand=True,
                    ),
                ],
                spacing=24,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=20,
            border_radius=24,
            bgcolor=ft.Colors.BLUE_GREY_50,
        )

    def _build_navigation(self) -> ft.Row:
        return ft.Row(
            controls=[
                self._nav_button("品种管理", "varieties"),
                self._nav_button("核桃管理", "walnuts", disabled=not self._has_varieties()),
                self._nav_button("开始配对", "matching", disabled=not self._has_varieties()),
            ],
            spacing=12,
        )

    def _nav_button(self, label: str, view_name: str, disabled: bool = False) -> ft.Control:
        selected = self.current_view == view_name
        button_cls = ft.FilledButton if selected else ft.OutlinedButton
        return button_cls(label, disabled=disabled, on_click=lambda _: self._switch_view(view_name))

    def _switch_view(self, view_name: str) -> None:
        self.current_view = view_name
        if self.selected_variety_id is None:
            varieties = repositories.list_varieties()
            self.selected_variety_id = varieties[0]["id"] if varieties else None
        self.render()

    def _build_view(self) -> ft.Control:
        if self.current_view == "walnuts":
            return self._build_walnut_view()
        if self.current_view == "matching":
            return self._build_matching_view()
        return self._build_variety_view()

    def _has_varieties(self) -> bool:
        return len(repositories.list_varieties()) > 0

    def _ensure_selected_variety(self) -> int | None:
        varieties = repositories.list_varieties()
        if not varieties:
            self.selected_variety_id = None
            return None
        if self.selected_variety_id is None or not any(item["id"] == self.selected_variety_id for item in varieties):
            self.selected_variety_id = varieties[0]["id"]
        return self.selected_variety_id

    def _build_variety_view(self) -> ft.Control:
        name_field = ft.TextField(label="品种名称", width=220)
        prefix_field = ft.TextField(label="编号前缀", width=160)
        tolerance_field = ft.TextField(label="偏差值 (mm)", width=140, value="1.0")

        if self.form_state.editing_variety_id:
            variety = repositories.get_variety(self.form_state.editing_variety_id)
            if variety:
                name_field.value = variety["name"]
                prefix_field.value = variety["code_prefix"]
                tolerance_field.value = str(variety["tolerance_mm"])

        def save_variety(_: ft.ControlEvent) -> None:
            try:
                tolerance = float(tolerance_field.value.strip())
                if self.form_state.editing_variety_id:
                    repositories.update_variety(
                        self.form_state.editing_variety_id,
                        name_field.value,
                        prefix_field.value,
                        tolerance,
                    )
                    self.status_message = "品种已更新"
                else:
                    variety_id = repositories.create_variety(name_field.value, prefix_field.value, tolerance)
                    self.selected_variety_id = variety_id
                    self.status_message = "品种已创建"
                self.form_state.editing_variety_id = None
                self.render()
            except Exception as exc:
                self.status_message = f"保存品种失败: {exc}"
                self.render()

        variety_cards: list[ft.Control] = []
        for variety in repositories.list_varieties():
            def edit_variety(_: ft.ControlEvent, variety_id: int = variety["id"]) -> None:
                self.form_state.editing_variety_id = variety_id
                self.render()

            def choose_variety(_: ft.ControlEvent, variety_id: int = variety["id"]) -> None:
                self.selected_variety_id = variety_id
                self.status_message = f"已切换到 {variety['name']}"
                self.render()

            def remove_variety(_: ft.ControlEvent, variety_id: int = variety["id"]) -> None:
                repositories.delete_variety(variety_id)
                self.status_message = "品种已删除"
                if self.selected_variety_id == variety_id:
                    self.selected_variety_id = None
                if self.form_state.editing_variety_id == variety_id:
                    self.form_state.editing_variety_id = None
                self.render()

            variety_cards.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(variety["name"], size=18, weight=ft.FontWeight.BOLD),
                                        ft.Container(expand=True),
                                        ft.Text(f"前缀 {variety['code_prefix']}"),
                                        ft.Text(f"偏差 {variety['tolerance_mm']}mm"),
                                    ]
                                ),
                                ft.Row(
                                    controls=[
                                        ft.TextButton("选中", on_click=choose_variety),
                                        ft.TextButton("编辑", on_click=edit_variety),
                                        ft.TextButton("删除", on_click=remove_variety),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            spacing=8,
                        ),
                        padding=16,
                    )
                )
            )

        return ft.Column(
            controls=[
                section_title("品种管理"),
                ft.Row(
                    controls=[
                        name_field,
                        prefix_field,
                        tolerance_field,
                        ft.FilledButton("保存品种", on_click=save_variety),
                    ],
                    wrap=True,
                    spacing=12,
                ),
                ft.Divider(),
                ft.Column(controls=variety_cards or [status_text("还没有品种，请先创建。")], spacing=12),
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def _build_variety_selector(self) -> ft.Dropdown:
        selected_variety = self._ensure_selected_variety()
        dropdown = ft.Dropdown(
            label="当前品种",
            width=260,
            value=str(selected_variety) if selected_variety else None,
            options=[
                ft.DropdownOption(str(variety["id"]), variety["name"])
                for variety in repositories.list_varieties()
            ],
            on_select=self._handle_variety_change,
        )
        return dropdown

    def _handle_variety_change(self, event: ft.ControlEvent) -> None:
        if event.control.value:
            self.selected_variety_id = int(event.control.value)
            self.form_state.editing_walnut_id = None
            self.status_message = "已切换品种"
            self.render()

    def _build_walnut_view(self) -> ft.Control:
        variety_id = self._ensure_selected_variety()
        if variety_id is None:
            return status_text("请先创建品种后再录入核桃。")

        serial_mode = ft.Dropdown(
            label="编号方式",
            width=180,
            value=SerialMode.AUTO.value,
            options=[
                ft.DropdownOption(SerialMode.AUTO.value, "自动生成"),
                ft.DropdownOption(SerialMode.MANUAL.value, "手动输入"),
            ],
        )
        serial_no = ft.TextField(label="编号", width=220, read_only=True, value=next_serial_no(variety_id))
        edge_mm = ft.TextField(label="边 (mm)", width=120, keyboard_type=ft.KeyboardType.NUMBER)
        belly_mm = ft.TextField(label="肚 (mm)", width=120, keyboard_type=ft.KeyboardType.NUMBER)
        height_mm = ft.TextField(label="高 (mm)", width=120, keyboard_type=ft.KeyboardType.NUMBER)
        weight_g = ft.TextField(label="克重 (g)", width=120, keyboard_type=ft.KeyboardType.NUMBER)
        defect_level = ft.Dropdown(
            label="瑕疵",
            width=160,
            value=DefectLevel.NONE.value,
            options=[
                ft.DropdownOption(DefectLevel.NONE.value, "无"),
                ft.DropdownOption(DefectLevel.LIGHT.value, "轻"),
                ft.DropdownOption(DefectLevel.MEDIUM.value, "中"),
                ft.DropdownOption(DefectLevel.HEAVY.value, "重"),
            ],
        )
        notes = ft.TextField(label="备注", multiline=True, min_lines=2, width=320)

        def refresh_serial_field(_: ft.ControlEvent | None = None) -> None:
            if serial_mode.value == SerialMode.MANUAL.value:
                serial_no.read_only = False
                serial_no.value = ""
            else:
                serial_no.read_only = True
                serial_no.value = next_serial_no(variety_id)
            self.page.update()

        serial_mode.on_select = refresh_serial_field

        if self.form_state.editing_walnut_id:
            walnut = repositories.get_walnut(self.form_state.editing_walnut_id)
            if walnut:
                serial_mode.value = walnut["serial_mode"]
                serial_no.value = walnut["serial_no"]
                serial_no.read_only = walnut["serial_mode"] == SerialMode.AUTO.value
                edge_mm.value = str(walnut["edge_mm"])
                belly_mm.value = str(walnut["belly_mm"])
                height_mm.value = str(walnut["height_mm"])
                weight_g.value = str(walnut["weight_g"])
                defect_level.value = walnut["defect_level"]
                notes.value = walnut["notes"] or ""

        def save_walnut(_: ft.ControlEvent) -> None:
            try:
                payload = {
                    "variety_id": variety_id,
                    "serial_mode": serial_mode.value,
                    "serial_no": serial_no.value.strip() if serial_mode.value == SerialMode.MANUAL.value else next_serial_no(variety_id),
                    "edge_mm": float(edge_mm.value),
                    "belly_mm": float(belly_mm.value),
                    "height_mm": float(height_mm.value),
                    "weight_g": float(weight_g.value),
                    "defect_level": defect_level.value,
                    "notes": notes.value.strip() or None,
                }
                if self.form_state.editing_walnut_id:
                    if serial_mode.value == SerialMode.MANUAL.value:
                        payload["serial_no"] = serial_no.value.strip()
                    else:
                        payload["serial_no"] = repositories.get_walnut(self.form_state.editing_walnut_id)["serial_no"]
                    repositories.update_walnut(self.form_state.editing_walnut_id, payload)
                    self.status_message = "核桃已更新"
                else:
                    repositories.create_walnut(payload)
                    self.status_message = "核桃已创建"
                self.form_state.editing_walnut_id = None
                self.render()
            except Exception as exc:
                self.status_message = f"保存核桃失败: {exc}"
                self.render()

        walnut_cards: list[ft.Control] = []
        for walnut in repositories.list_walnuts(variety_id=variety_id, include_locked=True):
            def edit_walnut(_: ft.ControlEvent, walnut_id: int = walnut["id"]) -> None:
                self.form_state.editing_walnut_id = walnut_id
                self.render()

            def remove_walnut(_: ft.ControlEvent, walnut_id: int = walnut["id"]) -> None:
                repositories.delete_walnut(walnut_id)
                self.status_message = "核桃已删除"
                if self.form_state.editing_walnut_id == walnut_id:
                    self.form_state.editing_walnut_id = None
                self.render()

            walnut_cards.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(walnut["serial_no"], size=18, weight=ft.FontWeight.BOLD),
                                        ft.Container(expand=True),
                                        ft.Text("已锁定" if walnut["is_locked"] else "未锁定"),
                                        ft.Text(f"瑕疵 {walnut['defect_level']}"),
                                    ]
                                ),
                                ft.Row(
                                    controls=[
                                        labeled_metric("边", f"{walnut['edge_mm']}"),
                                        labeled_metric("肚", f"{walnut['belly_mm']}"),
                                        labeled_metric("高", f"{walnut['height_mm']}"),
                                        labeled_metric("克重", f"{walnut['weight_g']}"),
                                    ],
                                    spacing=20,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.TextButton("编辑", on_click=edit_walnut),
                                        ft.TextButton("删除", on_click=remove_walnut),
                                    ]
                                ),
                            ],
                            spacing=8,
                        ),
                        padding=16,
                    )
                )
            )

        return ft.Column(
            controls=[
                section_title("核桃管理"),
                self._build_variety_selector(),
                ft.Row(
                    controls=[
                        serial_mode,
                        serial_no,
                        edge_mm,
                        belly_mm,
                        height_mm,
                        weight_g,
                    ],
                    wrap=True,
                    spacing=12,
                ),
                ft.Row(
                    controls=[
                        defect_level,
                        notes,
                        ft.FilledButton("保存核桃", on_click=save_walnut),
                    ],
                    wrap=True,
                    spacing=12,
                ),
                ft.Divider(),
                ft.Column(controls=walnut_cards or [status_text("当前品种还没有核桃。")], spacing=12),
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def _build_matching_view(self) -> ft.Control:
        variety_id = self._ensure_selected_variety()
        if variety_id is None:
            return status_text("请先创建品种。")

        candidates_by_walnut = get_candidates_for_variety(variety_id)
        active_locks = {item["id"]: item for item in repositories.list_locked_pairs(variety_id=variety_id, active_only=True)}

        def run_matching(_: ft.ControlEvent) -> None:
            self.status_message = "候选配对已刷新"
            self.render()

        rows: list[ft.Control] = []
        for walnut in repositories.list_walnuts(variety_id=variety_id, include_locked=True):
            active_lock = repositories.get_active_lock_for_walnut(walnut["id"])

            row_controls: list[ft.Control] = [
                ft.Row(
                    controls=[
                        ft.Text(walnut["serial_no"], size=18, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        ft.Text(f"三维 {walnut['edge_mm']}/{walnut['belly_mm']}/{walnut['height_mm']}"),
                        ft.Text(f"克重 {walnut['weight_g']}g"),
                        ft.Text(f"瑕疵 {walnut['defect_level']}"),
                    ]
                )
            ]

            if active_lock:
                partner_id = active_lock["walnut_id_2"] if active_lock["walnut_id_1"] == walnut["id"] else active_lock["walnut_id_1"]
                partner = repositories.get_walnut(partner_id)

                def unlock(_: ft.ControlEvent, pair_id: int = active_lock["id"]) -> None:
                    repositories.unlock_pair(pair_id)
                    self.status_message = "配对已解除锁定"
                    self.render()

                row_controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text(f"已锁定配对：{partner['serial_no']}"),
                                ft.TextButton("解除锁定", on_click=unlock),
                            ],
                            spacing=12,
                        ),
                        bgcolor=ft.Colors.GREEN_50,
                        padding=12,
                        border_radius=8,
                    )
                )
            else:
                candidate_cards: list[ft.Control] = []
                for candidate in candidates_by_walnut.get(walnut["id"], []):
                    def lock(_: ft.ControlEvent, left_id: int = walnut["id"], right_id: int = candidate.walnut_id) -> None:
                        repositories.lock_pair(variety_id, left_id, right_id)
                        self.status_message = "配对已锁定"
                        self.render()

                    def blacklist(_: ft.ControlEvent, left_id: int = walnut["id"], right_id: int = candidate.walnut_id) -> None:
                        repositories.create_blacklist_pair(variety_id, left_id, right_id)
                        self.status_message = "已加入拉黑列表"
                        self.render()

                    candidate_cards.append(
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text(candidate.serial_no, weight=ft.FontWeight.BOLD),
                                            ft.Container(expand=True),
                                            ft.Text(f"{candidate.total_score:.1f} 分"),
                                        ]
                                    ),
                                    ft.Row(
                                        controls=[
                                            labeled_metric("边差", f"{candidate.edge_diff:.2f}"),
                                            labeled_metric("肚差", f"{candidate.belly_diff:.2f}"),
                                            labeled_metric("高差", f"{candidate.height_diff:.2f}"),
                                            labeled_metric("重差", f"{candidate.weight_diff:.2f}"),
                                        ],
                                        spacing=16,
                                    ),
                                    ft.Row(
                                        controls=[
                                            ft.TextButton("锁定", on_click=lock),
                                            ft.TextButton("拉黑", on_click=blacklist),
                                        ],
                                        spacing=8,
                                    ),
                                ],
                                spacing=8,
                            ),
                            padding=12,
                            bgcolor=ft.Colors.BLUE_GREY_50,
                            border_radius=8,
                        )
                    )
                row_controls.append(
                    ft.Column(
                        controls=candidate_cards or [status_text("没有满足偏差条件的候选。")],
                        spacing=8,
                    )
                )

            rows.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(controls=row_controls, spacing=12),
                        padding=16,
                    )
                )
            )

        return ft.Column(
            controls=[
                section_title("候选配对"),
                ft.Row(
                    controls=[
                        self._build_variety_selector(),
                        ft.FilledButton("开始配对", on_click=run_matching),
                    ],
                    spacing=12,
                ),
                ft.Divider(),
                ft.Column(controls=rows or [status_text("当前品种还没有核桃。")], spacing=12),
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
