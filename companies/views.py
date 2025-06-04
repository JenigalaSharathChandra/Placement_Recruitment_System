# ✅ Refactored Company App - companies/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.urls import reverse
import json

from accounts.decorators import recruiter_required
from accounts.models import Job, Application, Interview
from accounts.models import CompanyRecruiter
from accounts.models import ActivityLog
from django.core.exceptions import ObjectDoesNotExist

@recruiter_required
def company_dashboard(request):
    recruiter_profile = get_object_or_404(CompanyRecruiter, user=request.user)
    total_jobs = Job.objects.filter(recruiter=recruiter_profile).count()
    total_applications = Application.objects.filter(job__recruiter=recruiter_profile).count()
    pending_applications = Application.objects.filter(job__recruiter=recruiter_profile, status='pending').count()
    upcoming_interviews = Interview.objects.filter(application__job__recruiter=recruiter_profile, scheduled_at__gte=timezone.now()).count()

    return render(request, 'company/dashboard.html', {
        'total_jobs': total_jobs,
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'upcoming_interviews': upcoming_interviews,
    })

@recruiter_required
def post_job(request):
    try:
        recruiter = request.user.companyrecruiter
    except ObjectDoesNotExist:
        messages.error(request, "Recruiter profile not found.")
        return redirect('login')

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        criteria = request.POST.get('criteria')
        vacancies = request.POST.get('vacancies')

        try:
            vacancies = int(vacancies)
            Job.objects.create(
                recruiter=recruiter,
                title=title,
                description=description,
                criteria=criteria,
                vacancies=vacancies
            )

            ActivityLog.objects.create(
                user=request.user,
                activity_type="Job Posted",
                description=f"{title} by {recruiter.company_name}"
            )
            messages.success(request, "Job posted successfully.")
            return redirect('company_dashboard')

        except (ValueError, TypeError):
            messages.error(request, "Invalid number of vacancies.")

    return render(request, 'company/post_job.html')

@recruiter_required
def view_applicants(request):
    recruiter = CompanyRecruiter.objects.get(user=request.user)
    jobs = Job.objects.filter(recruiter=recruiter)

    job_id = request.GET.get('job_id')
    applications = Application.objects.filter(job__recruiter=recruiter).select_related('student__user', 'job')

    if job_id:
        applications = applications.filter(job__id=job_id)

    paginator = Paginator(applications, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.method == 'POST':
        application_id = request.POST.get('application_id')
        new_status = request.POST.get('status')

        try:
            application = Application.objects.get(id=application_id, job__recruiter=recruiter)
            application.status = new_status
            application.save()
        except Application.DoesNotExist:
            pass

        url = reverse('view_applicants')
        params = ''
        if job_id:
            params += f'?job_id={job_id}'
            if page_number:
                params += f'&page={page_number}'
        elif page_number:
            params += f'?page={page_number}'
        return redirect(url + params)

    return render(request, 'company/view_applicants.html', {
        'applications': page_obj,
        'job_list': jobs,
        'page_obj': page_obj,
    })

@recruiter_required
def update_application_status(request):
    if request.method == 'POST':
        app_id = request.POST.get('application_id')
        new_status = request.POST.get('status')

        try:
            application = Application.objects.get(id=app_id)
            application.status = new_status
            application.save()
            return JsonResponse({'success': True})
        except Application.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Application not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@recruiter_required
def schedule_interviews(request):
    recruiter = CompanyRecruiter.objects.get(user=request.user)
    applications = Application.objects.filter(job__recruiter=recruiter, status='shortlisted').select_related('student__user', 'job')
    all_interviews = Interview.objects.filter(application__job__recruiter=recruiter).select_related('application__student__user', 'application__job').order_by('-scheduled_at')
    paginator = Paginator(all_interviews, 5)
    page_number = request.GET.get('page')
    interviews = paginator.get_page(page_number)
    return render(request, 'company/schedule_interviews.html', {
        'applications': applications,
        'interviews': interviews,
        'paginator': paginator,
    })

@csrf_exempt
@require_POST
@recruiter_required
def schedule_interview_form(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    try:
        data = json.loads(request.body)
        scheduled_at = data.get('scheduled_at')
        meeting_link = data.get('meeting_link')
        notes = data.get('notes')
        Interview.objects.create(
            application=application,
            scheduled_at=scheduled_at,
            meeting_link=meeting_link,
            notes=notes
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@recruiter_required
@csrf_exempt
def edit_interview(request, interview_id):
    if request.method == 'POST':
        try:
            interview = Interview.objects.get(id=interview_id)
            data = json.loads(request.body)
            interview.scheduled_at = data.get('scheduled_at')
            interview.meeting_link = data.get('meeting_link', '')
            interview.notes = data.get('notes', '')
            interview.save()
            return JsonResponse({'success': True})
        except Interview.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Interview not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@csrf_exempt
@require_POST
def update_interview_status(request, interview_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get("status")
            interview = Interview.objects.get(id=interview_id)
            interview.status = new_status
            interview.save()
            return JsonResponse({"success": True})
        except Interview.DoesNotExist:
            return JsonResponse({"success": False, "error": "Interview not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@csrf_exempt
@require_POST
@recruiter_required
def delete_interview(request, interview_id):
    try:
        interview = Interview.objects.get(id=interview_id)
        interview.delete()
        return JsonResponse({'success': True})
    except Interview.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Interview not found'})
