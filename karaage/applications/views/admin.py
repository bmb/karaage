# Copyright 2007-2010 VPAC
#
# This file is part of Karaage.
#
# Karaage is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Karaage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Karaage  If not, see <http://www.gnu.org/licenses/>.

from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.http import HttpResponseRedirect, Http404
from django.contrib.auth.decorators import permission_required, login_required
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from andsome.util.filterspecs import Filter, FilterBar

from karaage.people.models import Person
from karaage.applications.models import UserApplication, Applicant, Application
from karaage.applications.forms import AdminInviteUserApplicationForm, ApplicantForm
from karaage.applications.emails import send_user_invite_email, send_account_approved_email

@permission_required('applications.add_userapplication')
def send_invitation(request):
    
    application = None

    if request.method == 'POST':
        form = AdminInviteUserApplicationForm(request.POST, instance=application)

        if form.is_valid():
            email = form.cleaned_data['email']
            existing = Person.active.filter(user__email=email)
            if existing and not request.REQUEST.has_key('existing'):
                return render_to_response('applications/userapplication_invite_existing.html', {'form': form, 'email': email}, context_instance=RequestContext(request)) 
            application = form.save(commit=False)
            try:
                applicant = Person.active.get(user__email=email)
            except Person.DoesNotExist:
                applicant, created = Applicant.objects.get_or_create(email=email)

            application.applicant = applicant
            application.save()
            if application.content_type.model == 'person':
                application.approve()
                send_account_approved_email(application)
                messages.info(request, "%s was added to project %s directly since they have an existing account." % (application.applicant, application.project))
                return HttpResponseRedirect(application.applicant.get_absolute_url())
            send_user_invite_email(application)
            messages.info(request, "Invitation sent to %s." % email)
            return HttpResponseRedirect(application.get_absolute_url())
        
    else:
        form = AdminInviteUserApplicationForm(instance=application)

    return render_to_response('applications/userapplication_invite_form.html', {'form': form, 'application': application}, context_instance=RequestContext(request)) 

@login_required
def application_list(request, queryset=UserApplication.objects.select_related().all(), template_name='applications/application_list.html'):

    querystring = request.META.get('QUERY_STRING', '')

    apps = queryset

    page_no = int(request.GET.get('page', 1))

    if request.REQUEST.has_key('state'):
        apps = apps.filter(state=request.GET['state'])

    if request.method == 'POST':
        new_data = request.POST.copy()
        terms = new_data['search'].lower()
        query = Q()
        for term in terms.split(' '):
            q = Q(created_by__user__first_name__icontains=term) | Q(created_by__user__last_name__icontains=term) | Q(project__pid__icontains=term)
            query = query & q

        apps = apps.filter(query)
    else:
        terms = ""

    filter_list = []
    filter_list.append(Filter(request, 'state', UserApplication.APPLICATION_STATES))
    filter_bar = FilterBar(request, filter_list)

    p = Paginator(apps, 50)
    page = p.page(page_no)

    return render_to_response(template_name, {'page': page, 'filter_bar': filter_bar}, context_instance=RequestContext(request))

@permission_required('applications.change_application')
def approve_userapplication(request, application_id):
    application = get_object_or_404(UserApplication, pk=application_id)

    if application.state != Application.WAITING_FOR_ADMIN:
        raise Http404
    if request.method == 'POST':
        person = application.approve()
        send_account_approved_email(application)
        messages.info(request, "Application approved successfully")
        return HttpResponseRedirect(person.get_absolute_url())

    form = None

    return render_to_response('applications/approve_application.html', {'form': form, 'application': application}, context_instance=RequestContext(request))


@permission_required('applications.delete_application')
def decline_userapplication(request, application_id):
    application = get_object_or_404(UserApplication, pk=application_id)

    if application.state != Application.WAITING_FOR_ADMIN:
        raise Http404
    if request.method == 'POST':
        send_account_rejected_email(application)
        application.delete()
        return HttpResponseRedirect(reverse('kg_user_profile'))

    return render_to_response('applications/confirm_decline.html', {'application': application}, context_instance=RequestContext(request))


@login_required
def userapplication_detail(request, application_id):
    application = get_object_or_404(UserApplication, pk=application_id)

    return render_to_response('applications/adminapplication_detail.html', {'application': application}, context_instance=RequestContext(request))

