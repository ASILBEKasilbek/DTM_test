from django.contrib import admin

# Register your models here.
from .models import Subject, Topic, Question, TestSession, UserAnswer, Result, UserProfile



admin.site.register(Subject)
admin.site.register(Topic)
admin.site.register(Question)
admin.site.register(TestSession)
admin.site.register(UserAnswer)
admin.site.register(Result)
admin.site.register(UserProfile)