from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Boolean, Float, Text, func
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship
from jose import jwt, JWTError
from datetime import datetime, date, timedelta
from typing import List, Optional
from pydantic import BaseModel
import hashlib
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

SECRET = "your-super-secret-key-change-in-production"
ALGO = "HS256"

app = FastAPI(title="EdWay Complete LMS", version="3.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database
engine = create_engine("sqlite:///./EdWay_complete.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

# Password hashing
def hash_password(password: str) -> str:
    salt = "EdWay_salt_2024"
    return hashlib.sha256((password + salt).encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

# ==================== MODELS ====================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # ADMIN, TEACHER, STUDENT
    name = Column(String, nullable=False)
    class_name = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships - fixed with foreign_keys
    submissions = relationship("Submission", foreign_keys="Submission.student_id", back_populates="student")
    attendance_records = relationship("Attendance", foreign_keys="Attendance.student_id", back_populates="student")
    notifications = relationship("Notification", foreign_keys="Notification.user_id", back_populates="user")
    created_assignments = relationship("Assignment", foreign_keys="Assignment.created_by", back_populates="creator")
    marked_attendance = relationship("Attendance", foreign_keys="Attendance.marked_by", back_populates="marker")

class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    deadline = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    max_score = Column(Integer, default=100)
    
    # Relationships
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_assignments")

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, default="")
    file_url = Column(String, default="")
    grade = Column(Float, nullable=True)
    feedback = Column(Text, default="")
    submitted_at = Column(DateTime, default=datetime.utcnow)
    is_late = Column(Boolean, default=False)
    
    # Relationships
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("User", foreign_keys=[student_id], back_populates="submissions")

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(String, nullable=False)
    status = Column(String, nullable=False)  # PRESENT, ABSENT, LATE
    marked_by = Column(Integer, ForeignKey("users.id"))
    remarks = Column(String, default="")
    marked_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships - fixed with foreign_keys
    student = relationship("User", foreign_keys=[student_id], back_populates="attendance_records")
    marker = relationship("User", foreign_keys=[marked_by], back_populates="marked_attendance")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String, default="info")  # assignment, grade, attendance, system
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    link = Column(String, default="")
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="notifications")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True)
    description = Column(Text, default="")
    teacher_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")

class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"))
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="active")
    
    # Relationships
    course = relationship("Course", back_populates="enrollments")

# Create tables
Base.metadata.create_all(bind=engine)

# ==================== PYDANTIC SCHEMAS ====================

class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: str
    class_name: Optional[str] = ""

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    class_name: Optional[str]
    is_active: bool
    created_at: str

class AssignmentCreate(BaseModel):
    title: str
    description: str
    deadline: str
    max_score: int = 100

class AssignmentResponse(BaseModel):
    id: int
    title: str
    description: str
    deadline: str
    max_score: int
    created_by: int
    created_at: str

class SubmissionCreate(BaseModel):
    assignment_id: int
    content: str

class SubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    assignment_title: Optional[str]
    student_id: int
    student_name: Optional[str]
    content: str
    grade: Optional[float]
    feedback: str
    submitted_at: str
    is_late: bool

class AttendanceCreate(BaseModel):
    student_id: int
    status: str
    remarks: Optional[str] = ""

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: str
    link: str

# ==================== UTILITIES ====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_token(email: str, role: str, user_id: int) -> str:
    payload = {
        "sub": email,
        "role": role,
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGO])
    except JWTError:
        raise HTTPException(401, "Invalid token")

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing authorization header")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    user = db.query(User).filter(User.email == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    return user

def require_role(user: User, allowed_roles: List[str]):
    if user.role not in allowed_roles:
        raise HTTPException(403, f"Forbidden: Requires {allowed_roles} role")

def create_notification(user_id: int, title: str, message: str, notif_type: str = "info", link: str = "", db: Session = None):
    """Helper to create notifications"""
    if db:
        notif = Notification(user_id=user_id, title=title, message=message, type=notif_type, link=link)
        db.add(notif)
        db.commit()

# ==================== INITIALIZE DEMO DATA ====================

def init_demo_data():
    db = SessionLocal()
    
    if db.query(User).count() > 0:
        db.close()
        return
    
    print("🌱 Seeding complete demo data...")
    
    # Create users
    users = [
        User(email="admin@edway.com", password=hash_password("admin123"), role="ADMIN", name="System Admin"),
        User(email="teacher@edway.com", password=hash_password("teacher123"), role="TEACHER", name="Prof. Williams"),
        User(email="teacher2@edway.com", password=hash_password("teacher123"), role="TEACHER", name="Dr. Sarah Johnson"),
        User(email="student@edway.com", password=hash_password("student123"), role="STUDENT", name="Alex Johnson", class_name="Grade 10-A"),
        User(email="student2@edway.com", password=hash_password("student123"), role="STUDENT", name="Emma Watson", class_name="Grade 10-A"),
        User(email="student3@edway.com", password=hash_password("student123"), role="STUDENT", name="James Carter", class_name="Grade 10-B"),
    ]
    for u in users:
        db.add(u)
    db.commit()
    
    # Get IDs
    teacher = db.query(User).filter(User.email == "teacher@edway.com").first()
    teacher2 = db.query(User).filter(User.email == "teacher2@edway.com").first()
    students = db.query(User).filter(User.role == "STUDENT").all()
    
    # Create courses
    courses = [
        Course(name="Computer Science 101", code="CS101", description="Introduction to programming", teacher_id=teacher.id),
        Course(name="Web Development", code="WD201", description="HTML, CSS, JavaScript", teacher_id=teacher.id),
        Course(name="Database Systems", code="DB301", description="SQL and database design", teacher_id=teacher2.id),
    ]
    for c in courses:
        db.add(c)
    db.commit()
    
    # Enroll students
    for student in students:
        for course in courses[:2]:
            enrollment = Enrollment(student_id=student.id, course_id=course.id)
            db.add(enrollment)
    db.commit()
    
    # Create assignments
    today = date.today()
    assignments = [
        Assignment(title="Python Basics", description="Variables, loops, functions", deadline=str(today + timedelta(days=5)), created_by=teacher.id, max_score=100),
        Assignment(title="HTML/CSS Project", description="Build a personal portfolio", deadline=str(today + timedelta(days=10)), created_by=teacher.id, max_score=100),
        Assignment(title="JavaScript Fundamentals", description="DOM manipulation and events", deadline=str(today + timedelta(days=15)), created_by=teacher.id, max_score=100),
        Assignment(title="SQL Queries", description="Write complex SQL queries", deadline=str(today + timedelta(days=20)), created_by=teacher2.id, max_score=100),
    ]
    for a in assignments:
        db.add(a)
    db.commit()
    
    # Get assignment IDs
    python_assign = assignments[0]
    
    # Create submissions
    for student in students[:2]:
        submission = Submission(
            assignment_id=python_assign.id,
            student_id=student.id,
            content="Completed all exercises with examples",
            grade=85 if student.id == students[0].id else None,
            submitted_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(submission)
    
    # Create attendance records
    for i in range(10):
        att_date = today - timedelta(days=i)
        for student in students:
            status = "PRESENT" if i % 5 != 0 else "ABSENT"
            attendance = Attendance(
                student_id=student.id,
                date=str(att_date),
                status=status,
                marked_by=teacher.id
            )
            db.add(attendance)
    
    # Create notifications
    for student in students:
        notifications = [
            Notification(user_id=student.id, title="Welcome to EdWay!", message="Start exploring your courses", type="system"),
            Notification(user_id=student.id, title="New Assignment", message=f"{python_assign.title} has been posted. Due: {python_assign.deadline}", type="assignment", link="/assignments"),
        ]
        for n in notifications:
            db.add(n)
    
    db.commit()
    db.close()
    print("✅ Complete demo data seeded!")
    print("\n📝 Demo Credentials:")
    print("   Admin: admin@edway.com / admin123")
    print("   Teacher: teacher@edway.com / teacher123")
    print("   Student: student@edway.com / student123")

@app.get("/")
async def root():
    if os.path.exists("login.html"):
        return FileResponse("login.html")
    return {"message": "EdWay LMS API is running. Access /docs for API documentation"}

@app.get("/login")
async def login_page():
    return FileResponse("login.html")

@app.get("/dashboard")
async def dashboard_page():
    return FileResponse("dashboard.html")

@app.get("/teacher")
async def teacher_page():
    return FileResponse("teacher.html")

@app.get("/login.html")
async def login_html():
    return FileResponse("login.html")

@app.get("/dashboard.html")
async def dashboard_html():
    return FileResponse("dashboard.html")

# Add this to main.py - Teacher can view all students
@app.get("/students")
def get_all_students(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Allow TEACHER and ADMIN to view students
    require_role(current_user, ["TEACHER", "ADMIN"])
    
    students = db.query(User).filter(User.role == "STUDENT", User.is_active == True).all()
    return [{"id": s.id, "name": s.name, "email": s.email, "class_name": s.class_name} for s in students]

@app.get("/teacher.html")
async def teacher_html():
    return FileResponse("teacher.html")

@app.get("/admin.html")
async def admin_page():
    return FileResponse("admin.html")

@app.on_event("startup")
def on_startup():
    init_demo_data()

# ==================== AUTHENTICATION ====================

@app.post("/login")
def login(email: str = Query(...), password: str = Query(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(401, "Invalid credentials")
    
    token = create_token(user.email, user.role, user.id)
    return {
        "token": token,
        "role": user.role.lower(),
        "user_id": user.id,
        "name": user.name,
        "email": user.email
    }

@app.post("/signup")
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(400, "Email already exists")
    
    user = User(
        email=user_data.email,
        password=hash_password(user_data.password),
        name=user_data.name,
        role=user_data.role,
        class_name=user_data.class_name
    )
    db.add(user)
    db.commit()
    
    create_notification(user.id, "Welcome to EdWay!", f"Welcome {user.name}! Start exploring your courses.", "system", db=db)
    
    return {"msg": "User created", "user_id": user.id}

# ==================== USER MANAGEMENT (ADMIN) ====================

@app.get("/admin/users")
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["ADMIN"])
    users = db.query(User).all()
    return [{"id": u.id, "email": u.email, "name": u.name, "role": u.role, "class_name": u.class_name, "is_active": u.is_active} for u in users]

@app.post("/admin/users")
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["ADMIN"])
    
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(400, "Email already exists")
    
    user = User(
        email=user_data.email,
        password=hash_password(user_data.password),
        name=user_data.name,
        role=user_data.role,
        class_name=user_data.class_name
    )
    db.add(user)
    db.commit()
    return {"msg": "User created", "user_id": user.id}

@app.put("/admin/users/{user_id}")
def update_user(
    user_id: int,
    name: Optional[str] = None,
    role: Optional[str] = None,
    class_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["ADMIN"])
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    if name: user.name = name
    if role: user.role = role
    if class_name is not None: user.class_name = class_name
    if is_active is not None: user.is_active = is_active
    
    db.commit()
    return {"msg": "User updated"}

@app.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["ADMIN"])
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    db.delete(user)
    db.commit()
    return {"msg": "User deleted"}

# ==================== ASSIGNMENT MANAGEMENT ====================

@app.post("/assignments")
def create_assignment(
    title: str = Query(...),
    description: str = Query(""),
    deadline: str = Query(...),
    max_score: int = Query(100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["TEACHER", "ADMIN"])
    
    try:
        datetime.strptime(deadline, "%Y-%m-%d")
    except:
        raise HTTPException(400, "Invalid date format")
    
    assignment = Assignment(
        title=title,
        description=description,
        deadline=deadline,
        created_by=current_user.id,
        max_score=max_score
    )
    db.add(assignment)
    db.commit()
    
    students = db.query(User).filter(User.role == "STUDENT", User.is_active == True).all()
    for student in students:
        create_notification(
            student.id, 
            "New Assignment", 
            f"{title} has been posted. Due: {deadline}", 
            "assignment", 
            "/assignments",
            db
        )
    
    return {"id": assignment.id, "title": title, "description": description, "deadline": deadline, "max_score": max_score}

@app.get("/assignments")
def get_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    assignments = db.query(Assignment).all()
    return [{"id": a.id, "title": a.title, "description": a.description, "deadline": a.deadline, "max_score": a.max_score} for a in assignments]

@app.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["TEACHER", "ADMIN"])
    
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    
    db.delete(assignment)
    db.commit()
    return {"msg": "Assignment deleted"}

# ==================== SUBMISSIONS & GRADING ====================

@app.post("/submit")
def submit_assignment(
    assignment_id: int = Query(...),
    content: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["STUDENT"])
    
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    
    existing = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.student_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(400, "Already submitted")
    
    is_late = datetime.now().date() > datetime.strptime(assignment.deadline, "%Y-%m-%d").date()
    
    submission = Submission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        content=content,
        is_late=is_late
    )
    db.add(submission)
    db.commit()
    
    create_notification(
        assignment.created_by,
        "New Submission",
        f"{current_user.name} submitted {assignment.title}",
        "submission",
        "/submissions",
        db
    )
    
    return {"id": submission.id, "msg": "Submission successful"}

@app.get("/submissions")
def list_submissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "STUDENT":
        submissions = db.query(Submission).filter(Submission.student_id == current_user.id).all()
        return [{
            "id": s.id,
            "assignment_id": s.assignment_id,
            "assignment_title": s.assignment.title if s.assignment else "Unknown",
            "content": s.content,
            "grade": s.grade,
            "feedback": s.feedback,
            "submitted_at": s.submitted_at.isoformat(),
            "is_late": s.is_late
        } for s in submissions]
    else:
        submissions = db.query(Submission).all()
        result = []
        for s in submissions:
            student = db.query(User).filter(User.id == s.student_id).first()
            result.append({
                "id": s.id,
                "assignment_id": s.assignment_id,
                "assignment_title": s.assignment.title if s.assignment else "Unknown",
                "student_id": s.student_id,
                "student_name": student.name if student else "Unknown",
                "content": s.content,
                "grade": s.grade,
                "feedback": s.feedback,
                "submitted_at": s.submitted_at.isoformat(),
                "is_late": s.is_late
            })
        return result

@app.put("/grade/{submission_id}")
def grade_submission(
    submission_id: int,
    grade: float = Query(...),
    feedback: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["TEACHER", "ADMIN"])
    
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(404, "Submission not found")
    
    max_score = submission.assignment.max_score if submission.assignment else 100
    if grade < 0 or grade > max_score:
        raise HTTPException(400, f"Grade must be between 0 and {max_score}")
    
    submission.grade = grade
    submission.feedback = feedback
    db.commit()
    
    create_notification(
        submission.student_id,
        "Assignment Graded",
        f"Your submission for {submission.assignment.title if submission.assignment else 'assignment'} received {grade}%",
        "grade",
        "/grades",
        db
    )
    
    return {"id": submission.id, "grade": grade, "feedback": feedback}

# ==================== ATTENDANCE MANAGEMENT ====================

@app.post("/attendance")
def mark_attendance(
    student_id: int = Query(...),
    status: str = Query(...),
    date_str: str = Query(default=None),
    remarks: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["TEACHER", "ADMIN"])
    
    if status not in ["PRESENT", "ABSENT", "LATE"]:
        raise HTTPException(400, "Status must be PRESENT, ABSENT, or LATE")
    
    att_date = date_str if date_str else str(date.today())
    
    try:
        datetime.strptime(att_date, "%Y-%m-%d")
    except:
        raise HTTPException(400, "Invalid date format")
    
    student = db.query(User).filter(User.id == student_id, User.role == "STUDENT").first()
    if not student:
        raise HTTPException(404, "Student not found")
    
    existing = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.date == att_date
    ).first()
    
    if existing:
        existing.status = status
        existing.remarks = remarks
        existing.marked_by = current_user.id
        db.commit()
        return {"msg": "Attendance updated"}
    
    attendance = Attendance(
        student_id=student_id,
        date=att_date,
        status=status,
        remarks=remarks,
        marked_by=current_user.id
    )
    db.add(attendance)
    db.commit()
    
    if status != "PRESENT":
        create_notification(
            student_id,
            "Attendance Alert",
            f"You were marked {status} on {att_date}. Reason: {remarks if remarks else 'No reason provided'}",
            "attendance",
            "/attendance",
            db
        )
    
    return {"msg": "Attendance marked"}

@app.get("/attendance")
def get_attendance(
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "STUDENT":
        records = db.query(Attendance).filter(Attendance.student_id == current_user.id).all()
        return [{"id": r.id, "date": r.date, "status": r.status, "remarks": r.remarks} for r in records]
    else:
        require_role(current_user, ["TEACHER", "ADMIN"])
        query = db.query(Attendance)
        if student_id:
            query = query.filter(Attendance.student_id == student_id)
        records = query.all()
        result = []
        for r in records:
            student = db.query(User).filter(User.id == r.student_id).first()
            result.append({
                "id": r.id,
                "student_id": r.student_id,
                "student_name": student.name if student else "Unknown",
                "date": r.date,
                "status": r.status,
                "remarks": r.remarks
            })
        return result

@app.get("/attendance/summary")
def get_attendance_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "STUDENT":
        records = db.query(Attendance).filter(Attendance.student_id == current_user.id).all()
    else:
        records = db.query(Attendance).all()
    
    total = len(records)
    present = sum(1 for r in records if r.status == "PRESENT")
    late = sum(1 for r in records if r.status == "LATE")
    absent = total - present - late
    
    return {
        "total_days": total,
        "present": present,
        "late": late,
        "absent": absent,
        "attendance_rate": round((present / total * 100) if total > 0 else 0, 1)
    }

# ==================== NOTIFICATIONS ====================

@app.get("/notifications")
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notifications = db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).all()
    return [{"id": n.id, "title": n.title, "message": n.message, "type": n.type, "is_read": n.is_read, "created_at": n.created_at.isoformat(), "link": n.link} for n in notifications]

@app.put("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notification = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user.id).first()
    if not notification:
        raise HTTPException(404, "Notification not found")
    
    notification.is_read = True
    db.commit()
    return {"msg": "Marked as read"}

@app.delete("/notifications/{notification_id}")
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notification = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user.id).first()
    if not notification:
        raise HTTPException(404, "Notification not found")
    
    db.delete(notification)
    db.commit()
    return {"msg": "Notification deleted"}

# ==================== ADMIN STATS ====================

@app.get("/admin/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["ADMIN"])
    
    total_users = db.query(User).count()
    total_students = db.query(User).filter(User.role == "STUDENT").count()
    total_teachers = db.query(User).filter(User.role == "TEACHER").count()
    total_assignments = db.query(Assignment).count()
    total_submissions = db.query(Submission).count()
    total_attendance = db.query(Attendance).count()
    
    return {
        "total_users": total_users,
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_assignments": total_assignments,
        "total_submissions": total_submissions,
        "total_attendance": total_attendance
    }

# ==================== COURSE MANAGEMENT ====================

@app.get("/courses")
def get_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "STUDENT":
        enrollments = db.query(Enrollment).filter(Enrollment.student_id == current_user.id).all()
        course_ids = [e.course_id for e in enrollments]
        courses = db.query(Course).filter(Course.id.in_(course_ids)).all()
    else:
        courses = db.query(Course).all()
    
    return [{"id": c.id, "name": c.name, "code": c.code, "description": c.description} for c in courses]

# ==================== HEALTH CHECK ====================

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("🚀 Starting EdWay Complete LMS Backend")
    print("=" * 50)
    print("📍 API available at: http://127.0.0.1:8000")
    print("📚 API Documentation: http://127.0.0.1:8000/docs")
    print("-" * 50)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)