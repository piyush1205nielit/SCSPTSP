from django.db import models  
# Create your models here.
class studentdata(models.Model):
    mode=[
        ("offline","offline"),
        ("online","online"),
    ]
    caste=[
        ("OBC","OBC"),
        ("SC","SC"),
        ("ST","ST"),
        ("PWD","PWD"),
        ("GENERAL","GENERAL")
    ]

    centers=[
        ("inderlok","inderlok"),
        ("janakpuri","janakpuri"),
        ("karkardooma","karkardooma")
    ]
    session=models.DateField()
    name=models.CharField(max_length=30)
    course_name=models.CharField(max_length=50)
    course_hour=models.PositiveIntegerField()
    scheme=models.CharField(max_length=50)
    mode=models.CharField(max_length=10,choices=mode)
    caste_category=models.CharField(max_length=10,choices=caste)
    center_name=models.CharField(max_length=30,choices=centers)
    trained=models.BooleanField(default=False)
    certified=models.BooleanField(default=False)
    placed=models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}-{self.course_name}({self.caste_category})"


