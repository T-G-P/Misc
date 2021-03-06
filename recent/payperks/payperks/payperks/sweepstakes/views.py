from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views.decorators.csrf import csrf_exempt
from sweepstakes.models import Sweep, Drawing
from .utils import admins_only, users_only, randint


@csrf_exempt
@login_required
@users_only
@require_http_methods(["POST"])
def earn_points(request):
    user = request.user

    unclaimed_drawing = user.drawing_set.\
        filter(is_winner=True).\
        filter(prize_claimed=False).\
        first()

    if unclaimed_drawing:
        response = {
            'status': (
                'Please claim your prize before'
                ' entering the next sweep!'
            )
        }
        context_instance = RequestContext(request)
        return render_to_response("points.html",
                                  response,
                                  context_instance=context_instance)

    try:
        current_drawing = Drawing.objects.\
            filter(user=user).\
            filter(is_open=True).\
            latest('id')
    except Drawing.DoesNotExist:
        try:
            current_sweep = Sweep.objects.\
                filter(completed=False).\
                latest('id')
        except Sweep.DoesNotExist:
            current_sweep = Sweep(user=user)
            current_sweep.save()

        current_drawing = Drawing(user=user,
                                  sweep=current_sweep,
                                  points=randint(0, 999999))
        user.drawing_set.add(current_drawing)

        response = {
            'status': 'Total Points: {}'.format(
                current_drawing.points
            )
        }

    else:
        response = {
            'status': (
                'You already have an open drawing'
                ' with {} points'.format(current_drawing.points)
            )
        }

    context_instance = RequestContext(request)

    return render_to_response("points.html",
                              response,
                              context_instance=context_instance)


@csrf_exempt
@login_required
@admins_only
@require_http_methods(["POST"])
def run_sweeps(request):
    try:
        current_sweep = Sweep.objects.\
            filter(completed=False).\
            latest('id')
    except Sweep.DoesNotExist:
        response = {'status': 'No drawings entered'}
    else:
        current_sweep.completed = True
        current_sweep.save()
        prize_amount = current_sweep.prize_amount
        num_prizes = current_sweep.num_prizes
        drawing_prize = prize_amount/num_prizes

        drawings = Drawing.objects.filter(is_open=True)

        current_sweep.drawing_set.add(*drawings.all())
        winning_drawings = drawings.\
            order_by('-points').\
            all()[:num_prizes]

        for drawing in drawings.all():
            if drawing in winning_drawings:
                drawing.is_winner = True
                drawing.prize_value = drawing_prize
            drawing.is_open = False
            drawing.save()

        winners = [
            {
                'username': drawing.user.username,
                'prize': int(drawing_prize)
            }
            for drawing in winning_drawings
        ]

        response = {
            'status': (
                'Sweep Completed. '
                '{} prize(s) available, '
                '{} prize(s) awarded'.format(num_prizes, len(winning_drawings))
            ),
            'winners': winners
        }

    context_instance = RequestContext(request)
    return render_to_response("sweeps.html",
                              response,
                              context_instance=context_instance)


@csrf_exempt
@login_required
@users_only
@require_http_methods(["POST", "GET"])
def check_or_claim_prize(request):
    user = request.user
    try:
        drawing = Drawing.objects.filter(user=user).latest('id')
    except Drawing.DoesNotExist:
        response = {'status': 'You have no drawings'}
        return render_to_response('prize.html', response)

    if request.method == 'GET':
        if drawing.is_winner and not drawing.prize_claimed:
            response = {'status': 'You Won. Please claim your prize'}

        elif drawing.is_winner or not drawing.is_open:
            response = {'status': 'Sweep ended. Enter a new drawing!'}

        elif drawing.is_open:
            response = {'status': 'Current drawing is still open'}

    elif request.method == 'POST':
        if drawing.is_winner and drawing.prize_claimed:
            response = {'status': 'Prize already claimed'}

        elif drawing.is_open:
            response = {'status': 'No prize available to claim yet'}
        else:
            drawing.prize_claimed = True
            drawing.save()
            address = '{} {} {}'.format(user.userprofile.street,
                                        user.userprofile.city,
                                        user.userprofile.state)
            response = {
                'status': 'Payment of {} sent to {}'.format(
                    drawing.prize_value,
                    address
                )
            }

    if not drawing.is_open and not drawing.is_winner:
        response = {'status': 'You Lost'}

    context_instance = RequestContext(request)
    return render_to_response("prize.html",
                              response,
                              context_instance=context_instance)
