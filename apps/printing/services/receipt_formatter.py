from django.utils import timezone

WIDTH = 42  # 80mm paper @ 12x24 font ≈ 42 chars


def _line(char="-"):
    return char * WIDTH


def _center(text):
    return text.center(WIDTH)[:WIDTH]


def _left_right(left, right):
    right = str(right)
    left = str(left)
    max_left = WIDTH - len(right) - 1
    if len(left) > max_left:
        left = left[:max_left - 1] + "…"
    return f"{left:<{WIDTH - len(right)}}{right}"


def format_receipt(order) -> str:
    lines = []

    # ── Header ────────────────────────────────────────────────
    cafe = order.cafe
    cafe_name = cafe.name if cafe else "ARABICA"

    lines.append(_line("═"))
    lines.append(_center(cafe_name.upper()))
    if cafe and cafe.address:
        lines.append(_center(cafe.address))
    if cafe and cafe.phone:
        lines.append(_center(cafe.phone))
    lines.append(_line("═"))

    # Order ID + date on one line
    created_local = timezone.localtime(order.created_at)
    date_str = created_local.strftime("%d.%m.%Y  %H:%M")
    lines.append(_left_right(f"Заказ #{order.id}", date_str))
    lines.append(_line())

    # ── Items ─────────────────────────────────────────────────
    for item in order.items.select_related("product").all():
        name  = item.product.title
        qty   = item.quantity
        price = f"{item.final_price} с"
        lines.append(_left_right(f"{name} x{qty}", price))

        options = item.product_options.get("options", [])
        if options:
            opts_str = ", ".join(
                o.get("value", "") for o in options if o.get("value")
            )
            if opts_str:
                lines.append(f"  [{opts_str}]")

        comment = item.product_options.get("comment", "")
        if comment:
            lines.append(f"  Комм: {comment}")

    lines.append(_line())

    # ── Totals ────────────────────────────────────────────────
    if order.bonus_spent:
        lines.append(_left_right("Бонусы:", f"-{order.bonus_spent} с"))

    lines.append(_left_right("ИТОГО:", f"{order.total_price} с"))

    if order.bonus_earned:
        lines.append(_left_right("Начислено бонусов:", f"+{order.bonus_earned} б"))

    lines.append(_line())

    # ── Delivery / Customer ───────────────────────────────────
    if order.delivery_type == "delivery":
        lines.append("Тип: Доставка")
        if order.address:
            lines.append(f"Адрес: {order.address}")
        if order.delivery_time:
            lines.append(f"Время доставки: {order.delivery_time.strftime('%H:%M')}")
        if order.courier_comment:
            lines.append(f"Комментарий: {order.courier_comment}")
    else:
        lines.append("Тип: Самовывоз")

    if not order.user.phone_number.startswith("+00000"):
        name = " ".join(p for p in [order.user.first_name, order.user.last_name] if p)
        if name:
            lines.append(f"Клиент: {name}")
        lines.append(f"Тел: {order.user.phone_number}")

    # ── Footer ────────────────────────────────────────────────
    lines.append(_line("═"))
    lines.append(_center("Спасибо за заказ!"))
    lines.append(_line("═"))
    lines.append("")

    return "\n".join(lines)
