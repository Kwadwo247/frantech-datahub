"""
Financial Dashboard Views — Admin-only analytics and reporting.
"""

import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import (
    Sum, Count, Q, F, ExpressionWrapper, DecimalField, Avg
)
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from apps.orders.models import (
    Order, OrderStatus, OrderType, AfaRegistration, AfaStatus,
    ResultCheckerType, SMSLog
)
from apps.bundles.models import BundleCatalog


# ---------------------------------------------------------------------------
# Helper: date range
# ---------------------------------------------------------------------------

def _date_range(days: int):
    """Returns a list of date objects for the past `days` days (inclusive today)."""
    today = date.today()
    return [today - timedelta(days=i) for i in range(days - 1, -1, -1)]


# ---------------------------------------------------------------------------
# Main dashboard page
# ---------------------------------------------------------------------------

@method_decorator([staff_member_required, ensure_csrf_cookie], name='dispatch')
class DashboardView(View):
    template_name = 'admin/dashboard/index.html'

    def get(self, request):
        today = date.today()
        week_ago = today - timedelta(days=6)
        month_ago = today - timedelta(days=29)

        paid_statuses = [OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.COMPLETED]

        # ── Revenue summaries ──────────────────────────────────────────────
        qs_paid = Order.objects.filter(status__in=paid_statuses)

        today_revenue = qs_paid.filter(
            created_at__date=today
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        week_revenue = qs_paid.filter(
            created_at__date__gte=week_ago
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        month_revenue = qs_paid.filter(
            created_at__date__gte=month_ago
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        total_revenue = qs_paid.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # ── Gross profit ──────────────────────────────────────────────────
        # Data bundle profit: amount - bundle.vendor_price
        bundle_orders = qs_paid.filter(
            order_type=OrderType.DATA_BUNDLE,
            bundle__isnull=False
        ).annotate(
            cost=F('bundle__vendor_price')
        )
        bundle_revenue_sum = bundle_orders.aggregate(r=Sum('amount'))['r'] or Decimal('0')
        bundle_cost_sum = bundle_orders.aggregate(c=Sum('cost'))['c'] or Decimal('0')
        bundle_profit = bundle_revenue_sum - bundle_cost_sum

        # Result checker profit: amount - checker_type.vendor_price * quantity
        checker_orders = qs_paid.filter(
            order_type=OrderType.RESULT_CHECKER,
            checker_type__isnull=False
        ).annotate(
            cost=ExpressionWrapper(
                F('checker_type__vendor_price') * F('quantity'),
                output_field=DecimalField()
            )
        )
        checker_revenue_sum = checker_orders.aggregate(r=Sum('amount'))['r'] or Decimal('0')
        checker_cost_sum = checker_orders.aggregate(c=Sum('cost'))['c'] or Decimal('0')
        checker_profit = checker_revenue_sum - checker_cost_sum

        # AFA profit (static: revenue - 0 cost since no COGS tracked)
        afa_revenue_sum = qs_paid.filter(
            order_type=OrderType.AFA_REGISTRATION
        ).aggregate(r=Sum('amount'))['r'] or Decimal('0')
        afa_profit = afa_revenue_sum  # treat as pure profit since COGS is manual

        gross_profit = bundle_profit + checker_profit + afa_profit

        # ── Order counts ─────────────────────────────────────────────────
        order_counts = Order.objects.values('order_type').annotate(count=Count('id'))
        counts_by_type = {row['order_type']: row['count'] for row in order_counts}

        total_orders = Order.objects.count()
        paid_orders = qs_paid.count()
        failed_orders = Order.objects.filter(status=OrderStatus.FAILED).count()
        pending_orders = Order.objects.filter(status=OrderStatus.PENDING_PAYMENT).count()

        # ── AFA Pending registrations ─────────────────────────────────────
        afa_pending_list = AfaRegistration.objects.filter(
            status=AfaStatus.PENDING
        ).select_related('order').order_by('-created_at')[:20]

        # ── Stock alerts ─────────────────────────────────────────────────
        low_stock_threshold = 10
        checker_stock = ResultCheckerType.objects.filter(is_active=True).annotate(
            stock=Count('vouchers', filter=Q(vouchers__is_sold=False))
        ).order_by('stock')

        # ── SMS stats ────────────────────────────────────────────────────
        sms_sent_today = SMSLog.objects.filter(
            created_at__date=today, status='sent'
        ).count()
        sms_failed_today = SMSLog.objects.filter(
            created_at__date=today, status='failed'
        ).count()
        recent_sms = SMSLog.objects.select_related('order').order_by('-created_at')[:10]

        # ── Top bundles sold (by revenue) ─────────────────────────────────
        top_bundles = qs_paid.filter(
            order_type=OrderType.DATA_BUNDLE,
            bundle__isnull=False
        ).values('bundle__name', 'bundle__network').annotate(
            sales_count=Count('id'),
            revenue=Sum('amount')
        ).order_by('-revenue')[:5]

        # ── Recent orders ─────────────────────────────────────────────────
        recent_orders = Order.objects.select_related(
            'bundle', 'checker_type'
        ).order_by('-created_at')[:15]

        context = {
            # Revenue
            'today_revenue': today_revenue,
            'week_revenue': week_revenue,
            'month_revenue': month_revenue,
            'total_revenue': total_revenue,

            # Profit
            'gross_profit': gross_profit,
            'bundle_profit': bundle_profit,
            'checker_profit': checker_profit,
            'afa_profit': afa_profit,

            # Orders
            'total_orders': total_orders,
            'paid_orders': paid_orders,
            'failed_orders': failed_orders,
            'pending_orders': pending_orders,
            'counts_by_type': counts_by_type,

            # AFA
            'afa_pending_list': afa_pending_list,
            'afa_pending_count': afa_pending_list.count(),

            # Stock
            'checker_stock': checker_stock,
            'low_stock_threshold': low_stock_threshold,

            # SMS
            'sms_sent_today': sms_sent_today,
            'sms_failed_today': sms_failed_today,
            'recent_sms': recent_sms,

            # Top bundles
            'top_bundles': top_bundles,

            # Recent orders
            'recent_orders': recent_orders,

            # Admin context
            'title': 'Financial Dashboard',
            'has_permission': True,
        }
        return render(request, self.template_name, context)


# ---------------------------------------------------------------------------
# Chart Data API endpoints (JSON)
# ---------------------------------------------------------------------------

@staff_member_required
def chart_revenue_daily(request):
    """
    Returns last 30 days of daily paid revenue for the line chart.
    """
    days = int(request.GET.get('days', 14))
    days = max(7, min(days, 90))

    paid_statuses = [OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.COMPLETED]
    cutoff = date.today() - timedelta(days=days - 1)

    qs = (
        Order.objects
        .filter(status__in=paid_statuses, created_at__date__gte=cutoff)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(
            total=Sum('amount'),
            count=Count('id'),
        )
        .order_by('day')
    )

    # Build full date series with zero fill
    date_map = {row['day']: row for row in qs}
    labels = []
    revenue_data = []
    order_count_data = []

    for d in _date_range(days):
        labels.append(d.strftime('%d %b'))
        row = date_map.get(d)
        revenue_data.append(float(row['total']) if row else 0)
        order_count_data.append(row['count'] if row else 0)

    return JsonResponse({
        'labels': labels,
        'revenue': revenue_data,
        'orders': order_count_data,
    })


@staff_member_required
def chart_order_types(request):
    """
    Returns revenue breakdown by order type for the donut chart.
    """
    paid_statuses = [OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.COMPLETED]
    qs = (
        Order.objects
        .filter(status__in=paid_statuses)
        .values('order_type')
        .annotate(total=Sum('amount'), count=Count('id'))
    )
    labels = []
    revenue = []
    counts = []
    colors = {
        OrderType.DATA_BUNDLE: '#6366f1',
        OrderType.RESULT_CHECKER: '#f59e0b',
        OrderType.AFA_REGISTRATION: '#10b981',
    }
    type_labels = {
        OrderType.DATA_BUNDLE: 'Data Bundles',
        OrderType.RESULT_CHECKER: 'WAEC Checkers',
        OrderType.AFA_REGISTRATION: 'AFA Registration',
    }
    chart_colors = []
    for row in qs:
        ot = row['order_type']
        labels.append(type_labels.get(ot, ot))
        revenue.append(float(row['total']))
        counts.append(row['count'])
        chart_colors.append(colors.get(ot, '#94a3b8'))

    return JsonResponse({
        'labels': labels,
        'revenue': revenue,
        'counts': counts,
        'colors': chart_colors,
    })


@staff_member_required
def chart_network_breakdown(request):
    """
    Returns revenue breakdown by network for data bundle orders.
    """
    paid_statuses = [OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.COMPLETED]
    qs = (
        Order.objects
        .filter(status__in=paid_statuses, order_type=OrderType.DATA_BUNDLE)
        .values('network')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )
    labels = []
    revenue = []
    counts = []
    net_colors = {
        'mtn': '#fbbf24',
        'telecel': '#ef4444',
        'at_bigdata': '#3b82f6',
        'at_ishare': '#06b6d4',
    }
    net_labels = {
        'mtn': 'MTN',
        'telecel': 'Telecel',
        'at_bigdata': 'AirtelTigo Big Data',
        'at_ishare': 'AirtelTigo iShare',
    }
    chart_colors = []
    for row in qs:
        net = row['network']
        labels.append(net_labels.get(net, net.upper()))
        revenue.append(float(row['total']))
        counts.append(row['count'])
        chart_colors.append(net_colors.get(net, '#94a3b8'))

    return JsonResponse({
        'labels': labels,
        'revenue': revenue,
        'counts': counts,
        'colors': chart_colors,
    })


# ---------------------------------------------------------------------------
# AFA Batch Approval Action
# ---------------------------------------------------------------------------

@staff_member_required
def afa_batch_approve(request):
    """
    POST: Marks all pending AFA registrations as 'submitted'.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    updated = AfaRegistration.objects.filter(
        status=AfaStatus.PENDING
    ).update(status=AfaStatus.SUBMITTED)

    return JsonResponse({'success': True, 'updated': updated})


@staff_member_required
def afa_approve_single(request, pk):
    """
    POST: Marks a single AFA registration as 'submitted'.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        afa = AfaRegistration.objects.get(pk=pk, status=AfaStatus.PENDING)
        afa.status = AfaStatus.SUBMITTED
        afa.save(update_fields=['status'])
        return JsonResponse({'success': True, 'id': pk, 'status': 'submitted'})
    except AfaRegistration.DoesNotExist:
        return JsonResponse({'error': 'Not found or already processed'}, status=404)
