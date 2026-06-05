from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from storage.models import File, Folder

@login_required
def search_files(request):
    """Search files and folders"""
    query = request.GET.get('q', '').strip()
    file_type = request.GET.get('type', '')
    results = {'files': [], 'folders': []}
    
    if query:
        # Search files
        file_query = Q(name__icontains=query) | Q(original_name__icontains=query)
        files = File.objects.filter(file_query, owner=request.user)
        
        if file_type:
            files = files.filter(file_type__iexact=file_type)
        
        results['files'] = files.order_by('-uploaded_at')
        
        # Search folders
        folder_query = Q(name__icontains=query)
        results['folders'] = Folder.objects.filter(folder_query, owner=request.user).order_by('name')
    
    context = {
        'query': query,
        'file_type': file_type,
        'results': results,
        'file_types': File.objects.filter(owner=request.user)
                                  .values_list('file_type', flat=True)
                                  .distinct()
                                  .order_by('file_type') if query else [],
    }
    return render(request, 'search/search.html', context)