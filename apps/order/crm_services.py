from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.utils import timezone

from apps.order.models import CafeMembership, Order

User = get_user_model()


ACTIVE_ORDER_STATUSES = ("accepted", "ready", "on_the_way")


# ── Auth helpers ───────────────────────────────────────────────────────────────

def get_staff_membership(user):
    if not user.is_authenticated:
        return None
    try:
        membership = CafeMembership.objects.select_related("cafe").get(user=user)
    except CafeMembership.DoesNotExist:
        return None
    if membership.role != CafeMembership.Role.STAFF:
        return None
    return membership


# ── Couriers ───────────────────────────────────────────────────────────────────

def get_cafe_couriers(cafe):
    """
    Return User queryset of couriers for this cafe.
    Includes users with CafeMembership.role=COURIER in this cafe,
    OR users with is_courier=True who have any membership in this cafe.
    """
    cafe_member_ids = CafeMembership.objects.filter(cafe=cafe).values_list("user_id", flat=True)
    return (
        User.objects.filter(is_active=True)
        .filter(
            Q(cafe_membership__cafe=cafe, cafe_membership__role=CafeMembership.Role.COURIER)
            | Q(is_courier=True, id__in=cafe_member_ids)
        )
        .distinct()
        .order_by("first_name", "phone_number")
    )


def get_couriers_with_status(cafe):
    today = timezone.now().date()
    result = []
    for user in get_cafe_couriers(cafe):
        active = (
            Order.objects.filter(courier=user, cafe=cafe, status="on_the_way")
            .select_related("user")
            .first()
        )
        delivered_today = Order.objects.filter(
            courier=user, cafe=cafe, status="delivered", delivered_at__date=today
        ).count()
        name = " ".join(p for p in [user.first_name, user.last_name] if p) or user.phone_number
        result.append({
            "id": user.id,
            "name": name,
            "phone_number": user.phone_number,
            "is_busy": active is not None,
            "active_order": {
                "id": active.id,
                "customer": " ".join(
                    p for p in [active.user.first_name, active.user.last_name] if p
                ) or active.user.phone_number,
                "address": active.address or "",
                "created_at": active.created_at.strftime("%H:%M"),
            } if active else None,
            "delivered_today": delivered_today,
        })
    return result


# ── Active orders ──────────────────────────────────────────────────────────────

def get_active_orders(cafe):
    return (
        Order.objects.select_related("user", "cafe", "courier")
        .prefetch_related("items__product")
        .filter(cafe=cafe, status__in=ACTIVE_ORDER_STATUSES)
        .order_by("created_at")
    )


def _get_print_status(order):
    job = order.print_jobs.order_by("-created_at").first()
    if job is None:
        return "none", None
    return job.status, job.id


def serialize_order(order):
    courier_name = ""
    if order.courier:
        courier_name = (
            " ".join(p for p in [order.courier.first_name, order.courier.last_name] if p)
            or order.courier.phone_number
        )
    customer_name = " ".join(
        p for p in [order.user.first_name, order.user.last_name] if p
    )
    print_status, print_job_id = _get_print_status(order)
    return {
        "id": order.id,
        "status": order.status,
        "status_label": order.get_status_display(),
        "delivery_type": order.delivery_type,
        "delivery_type_label": order.get_delivery_type_display(),
        "address": order.address or "",
        "delivery_time": order.delivery_time.strftime("%H:%M") if order.delivery_time else "",
        "courier_comment": order.courier_comment,
        "total_price": str(order.total_price),
        "created_at": order.created_at.strftime("%H:%M"),
        "created_at_iso": order.created_at.isoformat(),
        "ready_at_iso": order.ready_at.isoformat() if order.ready_at else None,
        "on_the_way_at_iso": order.on_the_way_at.isoformat() if order.on_the_way_at else None,
        "customer": {"phone_number": order.user.phone_number, "name": customer_name},
        "courier": {
            "id": order.courier_id,
            "phone_number": order.courier.phone_number if order.courier else "",
            "name": courier_name,
        },
        "print_status": print_status,
        "print_job_id": print_job_id,
        "items": [
            {
                "id": item.id,
                "product_title": item.product.title,
                "quantity": item.quantity,
                "options": item.product_options.get("options", []),
                "comment": item.product_options.get("comment", ""),
                "final_price": str(item.final_price),
            }
            for item in order.items.all()
        ],
    }


def serialize_active_orders(cafe):
    return [serialize_order(o) for o in get_active_orders(cafe)]


# ── History ────────────────────────────────────────────────────────────────────

def get_completed_orders_today(cafe):
    today = timezone.now().date()
    return (
        Order.objects.select_related("user", "courier")
        .prefetch_related("items__product")
        .filter(cafe=cafe, status="delivered", delivered_at__date=today)
        .order_by("-delivered_at")
    )


def serialize_completed_order(order):
    courier_name = ""
    if order.courier:
        courier_name = (
            " ".join(p for p in [order.courier.first_name, order.courier.last_name] if p)
            or order.courier.phone_number
        )
    customer_name = (
        " ".join(p for p in [order.user.first_name, order.user.last_name] if p)
        or order.user.phone_number
    )
    return {
        "id": order.id,
        "delivery_type": order.delivery_type,
        "delivery_type_label": order.get_delivery_type_display(),
        "total_price": str(order.total_price),
        "delivered_at": order.delivered_at.strftime("%H:%M") if order.delivered_at else "",
        "created_at": order.created_at.strftime("%H:%M"),
        "customer": {"name": customer_name, "phone_number": order.user.phone_number},
        "courier_name": courier_name,
        "items": [
            {
                "product_title": item.product.title,
                "quantity": item.quantity,
                "options": item.product_options.get("options", []),
                "final_price": str(item.final_price),
            }
            for item in order.items.all()
        ],
    }


# ── Stats ──────────────────────────────────────────────────────────────────────

def get_today_stats(cafe):
    today = timezone.now().date()
    delivered_qs = Order.objects.filter(
        cafe=cafe, status="delivered", delivered_at__date=today
    )
    revenue = delivered_qs.aggregate(total=Sum("total_price"))["total"] or 0
    return {
        "delivered_count": delivered_qs.count(),
        "revenue_today": int(revenue),
    }


# ── POS guest user ─────────────────────────────────────────────────────────────

def get_or_create_guest_user(cafe):
    phone = f"+00000{cafe.id:05d}"
    user, _ = User.objects.get_or_create(
        phone_number=phone,
        defaults={"first_name": "Гость", "last_name": "", "is_phone_verified": False},
    )
    return user


# ── WebSocket broadcast ────────────────────────────────────────────────────────

def broadcast_cafe_orders(cafe_id):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"cafe_orders_{cafe_id}",
        {"type": "orders.changed"},
    )
