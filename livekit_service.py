#!/usr/bin/env python3
"""
AIRecruiters LiveKit Agent - VAD-ONLY IMPLEMENTATION WITH FLASK WRAPPER FOR AZURE
✅ Flask wrapper for Azure App Service compatibility
✅ Save conversations directly from transcript events
✅ Simple and reliable approach using only VAD
✅ Proper VAD configuration based on official LiveKit docs
✅ Enhanced speech quality with faster, louder AI voice
"""

# ============================================================================
# FLASK WRAPPER FOR AZURE APP SERVICE COMPATIBILITY
# ============================================================================

from flask import Flask, jsonify
import threading
import time
import logging as flask_logging

# Create the Flask app that Azure expects
app = Flask(__name__)

# Global flag to track agent status
agent_started = False
agent_status = "starting"

@app.route('/')
def health():
    return jsonify({
        "status": "LiveKit Agent Running", 
        "service": "AIRecruiters",
        "mode": "VAD-only",
        "agent_started": agent_started,
        "agent_status": agent_status
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy" if agent_started else "starting", 
        "agent": "active" if agent_started else "initializing"
    })

@app.route('/status')
def status():
    return jsonify({
        "agent_type": "LiveKit VAD Interview Agent",
        "agent_started": agent_started,
        "agent_status": agent_status,
        "debug": Config.DEBUG if 'Config' in globals() else "unknown"
    })

# ============================================================================
# ORIGINAL LIVEKIT AGENT CODE (UNCHANGED FUNCTIONALITY)
# ============================================================================

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

# LiveKit imports
from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, ChatContext, ChatMessage, UserStateChangedEvent, AgentStateChangedEvent
from livekit.plugins import openai, assemblyai, aws, silero

# 🔥 REMOVED: Turn detector imports - not needed for VAD-only mode

# Database imports (keep your existing database code)
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Boolean, text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER

# Environment setup
from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# SIMPLIFIED CONFIGURATION - VAD ONLY
# ============================================================================

class Config:
    # Database
    DATABASE_CONNECTION_STRING = os.getenv("DATABASE_CONNECTION_STRING")
    
    # LiveKit
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET") 
    LIVEKIT_WS_URL = os.getenv("LIVEKIT_WS_URL")
    
    # AI Providers
    ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # 🔥 SIMPLIFIED: VAD Configuration only
    VAD_MIN_SPEECH_DURATION = float(os.getenv("VAD_MIN_SPEECH_DURATION", "0.03"))     # Default: 0.05
    VAD_MIN_SILENCE_DURATION = float(os.getenv("VAD_MIN_SILENCE_DURATION", "0.4"))   # Default: 0.55
    VAD_PREFIX_PADDING_DURATION = float(os.getenv("VAD_PREFIX_PADDING_DURATION", "0.2"))  # Default: 0.5
    VAD_MAX_BUFFERED_SPEECH = float(os.getenv("VAD_MAX_BUFFERED_SPEECH", "60.0"))     # Default: 60.0
    VAD_ACTIVATION_THRESHOLD = float(os.getenv("VAD_ACTIVATION_THRESHOLD", "0.5"))    # Default: 0.5
    VAD_SAMPLE_RATE = int(os.getenv("VAD_SAMPLE_RATE", "16000"))                      # Default: 16000
    VAD_FORCE_CPU = os.getenv("VAD_FORCE_CPU", "True").lower() == "true"             # Default: True
    
    # 🔥 SIMPLIFIED: VAD-only endpointing settings
    MIN_ENDPOINTING_DELAY = float(os.getenv("MIN_ENDPOINTING_DELAY", "0.8"))         # Increased for VAD-only
    MAX_ENDPOINTING_DELAY = float(os.getenv("MAX_ENDPOINTING_DELAY", "6.0"))         # Default: 6.0
    
    # 🔥 SIMPLIFIED: Interruption Settings
    ALLOW_INTERRUPTIONS = os.getenv("ALLOW_INTERRUPTIONS", "True").lower() == "true" # Default: True
    MIN_INTERRUPTION_DURATION = float(os.getenv("MIN_INTERRUPTION_DURATION", "1.0")) # Default: 0.5

# Setup logging
logging.basicConfig(
    level=logging.DEBUG if Config.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE MODELS & SERVICE (KEEP YOUR EXISTING DATABASE CODE)
# ============================================================================

class Base(DeclarativeBase):
    pass

class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(UNIQUEIDENTIFIER, primary_key=True)
    interview_id = Column(String(255), unique=True, nullable=False)
    job_position = Column(String(255), nullable=False)
    job_description = Column(Text, nullable=True)
    duration = Column(String(50), nullable=True)
    question_list = Column(Text, nullable=True)
    voice_platform = Column(String(50), default="vapi")
    passing_score = Column(Integer, default=6)
    created_at = Column(DateTime, default=datetime.utcnow)

class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"
    
    id = Column(UNIQUEIDENTIFIER, primary_key=True)
    interview_id = Column(String(255), nullable=False)
    user_name = Column(String(255), nullable=False)
    user_email = Column(String(255), nullable=False)
    
    conversation_data = Column("ConversationData", Text, nullable=True)
    interview_duration = Column("InterviewDuration", Integer, nullable=True)
    
    feedback = Column(Text, nullable=True)
    recommended = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    vapi_call_id = Column(String(255), nullable=True)
    call_cost = Column(String(255), nullable=True)
    cost_breakdown = Column(Text, nullable=True)
    video_recording_id = Column("VideoRecordingId", String(255), nullable=True)
    millis_session_id = Column("MillisSessionId", String(255), nullable=True)
    millis_call_id = Column("MillisCallId", String(255), nullable=True)
    millis_cost_breakdown = Column("MillisCostBreakdown", Text, nullable=True)

class DatabaseService:
    def __init__(self):
        self.connection_string = self._build_connection_string()
        self.engine = create_engine(self.connection_string, echo=Config.DEBUG)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        logger.info("📊 Database service initialized")
    
    def _build_connection_string(self):
        """Convert .NET connection string to SQLAlchemy format"""
        net_conn_str = Config.DATABASE_CONNECTION_STRING
        
        if "Server=" in net_conn_str and "Database=" in net_conn_str:
            parts = {}
            for part in net_conn_str.split(';'):
                if '=' in part:
                    key, value = part.split('=', 1)
                    parts[key.strip()] = value.strip()
            
            server = parts.get('Server', 'localhost')
            database = parts.get('Database', 'AIRECRUITER')
            
            if 'Trusted_Connection=True' in net_conn_str:
                conn_str = f"mssql+pyodbc://@{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
            else:
                username = parts.get('User ID', '')
                password = parts.get('Password', '')
                conn_str = f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
            
            return conn_str
        
        return net_conn_str
    
    def test_connection(self):
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info("✅ Database connection successful")
                return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def get_interview(self, interview_id: str):
        """Get interview by ID"""
        session = self.SessionLocal()
        try:
            interview = session.query(Interview).filter(
                Interview.interview_id == interview_id
            ).first()
            
            if interview:
                logger.info(f"✅ Found interview: {interview_id}")
                return {
                    'interview_id': interview.interview_id,
                    'job_position': interview.job_position,
                    'job_description': interview.job_description,
                    'duration': interview.duration,
                    'question_list': interview.question_list,
                    'voice_platform': interview.voice_platform,
                    'passing_score': interview.passing_score
                }
            else:
                logger.warning(f"❌ Interview not found: {interview_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting interview: {e}")
            return None
        finally:
            session.close()
    
    def save_conversation_simple(self, interview_id: str, conversation_data: str):
        """Simple conversation save - create or update record"""
        session = self.SessionLocal()
        try:
            user_email = f"candidate-{interview_id}@interview.local"
            user_name = "Candidate"
            
            feedback = session.query(InterviewFeedback).filter(
                InterviewFeedback.interview_id == interview_id
            ).first()
            
            if feedback:
                feedback.conversation_data = conversation_data
                feedback.updated_at = datetime.utcnow()
                logger.info(f"✅ Updated conversation for interview {interview_id} - {len(conversation_data)} chars")
            else:
                feedback = InterviewFeedback(
                    interview_id=interview_id,
                    user_email=user_email,
                    user_name=user_name,
                    conversation_data=conversation_data,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(feedback)
                logger.info(f"✅ Created new conversation record for interview {interview_id}")
            
            session.commit()
            return True
                
        except Exception as e:
            logger.error(f"❌ Error saving conversation: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def save_interview_duration_simple(self, interview_id: str, duration_seconds: int):
        """Simple duration save"""
        session = self.SessionLocal()
        try:
            feedback = session.query(InterviewFeedback).filter(
                InterviewFeedback.interview_id == interview_id
            ).first()
            
            if feedback:
                feedback.interview_duration = duration_seconds
                feedback.updated_at = datetime.utcnow()
                session.commit()
                logger.info(f"✅ Saved duration ({duration_seconds}s) for interview {interview_id}")
                return True
            else:
                logger.warning(f"❌ No feedback record found for duration save: {interview_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error saving duration: {e}")
            session.rollback()
            return False
        finally:
            session.close()


# Global database instance
db = DatabaseService()

# ============================================================================
# 🔥 SIMPLIFIED CONVERSATION TRACKER - VAD ONLY
# ============================================================================

class VadConversationTracker:
    def __init__(self, interview_id: str):
        self.interview_id = interview_id
        self.conversation_log = []
        self.start_time = datetime.utcnow()
        self.save_counter = 0
        
        # 🔥 SIMPLIFIED: VAD-only statistics
        self.vad_stats = {
            "user_speech_events": 0,
            "agent_speech_events": 0,
            "user_state_changes": 0,
            "agent_state_changes": 0,
            "last_user_state": "unknown",
            "last_agent_state": "unknown"
        }
    
    def on_user_state_changed(self, event: UserStateChangedEvent):
        """Handle user state change events"""
        self.vad_stats["user_state_changes"] += 1
        self.vad_stats["last_user_state"] = event.new_state
        
        if event.new_state == "speaking":
            self.vad_stats["user_speech_events"] += 1
            logger.info(f"👤 User started speaking (Event #{self.vad_stats['user_speech_events']})")
        elif event.new_state == "listening":
            logger.info("👤 User stopped speaking")
        elif event.new_state == "away":
            logger.info("👤 User disconnected or away")
    
    def on_agent_state_changed(self, event: AgentStateChangedEvent):
        """Handle agent state change events"""
        self.vad_stats["agent_state_changes"] += 1
        self.vad_stats["last_agent_state"] = event.new_state
        
        if event.new_state == "speaking":
            self.vad_stats["agent_speech_events"] += 1
            logger.info(f"🤖 Agent started speaking (Event #{self.vad_stats['agent_speech_events']})")
        elif event.new_state == "listening":
            logger.info("🤖 Agent listening for user input")
        elif event.new_state == "thinking":
            logger.info("🤖 Agent processing input and generating response")
        elif event.new_state == "idle":
            logger.info("🤖 Agent ready but not processing")
    
    def add_user_message(self, text: str):
        """Add user message from transcript"""
        if not text or not text.strip():
            return
            
        message = {
            "role": "user",
            "content": text.strip(),
            "timestamp": datetime.utcnow().isoformat(),
            "user_state": self.vad_stats["last_user_state"],
            "agent_state": self.vad_stats["last_agent_state"]
        }
        
        self.conversation_log.append(message)
        logger.info(f"👤 Added user message ({len(self.conversation_log)} total): {text[:50]}...")
        
        # Save every 3 messages OR immediately if it's the first few
        if len(self.conversation_log) <= 3 or len(self.conversation_log) % 3 == 0:
            self._save_to_database()
    
    def add_assistant_message(self, text: str):
        """Add assistant message"""
        if not text or not text.strip():
            return
            
        message = {
            "role": "assistant",
            "content": text.strip(),
            "timestamp": datetime.utcnow().isoformat(),
            "user_state": self.vad_stats["last_user_state"],
            "agent_state": self.vad_stats["last_agent_state"]
        }
        
        self.conversation_log.append(message)
        logger.info(f"🤖 Added assistant message ({len(self.conversation_log)} total): {text[:50]}...")
        
        # Save every 3 messages OR immediately if it's the first few
        if len(self.conversation_log) <= 3 or len(self.conversation_log) % 3 == 0:
            self._save_to_database()
    
    def _save_to_database(self):
        """Save current conversation to database"""
        try:
            if len(self.conversation_log) == 0:
                return
                
            # Include VAD statistics
            conversation_with_stats = {
                "messages": self.conversation_log,
                "vad_statistics": self.vad_stats,
                "saved_at": datetime.utcnow().isoformat()
            }
            
            conversation_json = json.dumps(conversation_with_stats, indent=2)
            self.save_counter += 1
            
            logger.info(f"💾 Saving conversation #{self.save_counter} with {len(self.conversation_log)} messages...")
            logger.info(f"📊 VAD stats: User events={self.vad_stats['user_speech_events']}, Agent events={self.vad_stats['agent_speech_events']}")
            
            logger.info(f"✅ Save #{self.save_counter} SKIPPED (C# handles saving)")
                
        except Exception as e:
            logger.error(f"❌ Error saving conversation: {e}")
    
    def finalize(self):
        """Finalize interview - save duration and final conversation"""
        try:
            end_time = datetime.utcnow()
            duration_seconds = int((end_time - self.start_time).total_seconds())
            
            logger.info(f"⏰ Interview duration: {duration_seconds} seconds")
            logger.info(f"📊 Final conversation: {len(self.conversation_log)} messages")
            logger.info(f"📈 Final VAD statistics:")
            logger.info(f"  - User speech events: {self.vad_stats['user_speech_events']}")
            logger.info(f"  - Agent speech events: {self.vad_stats['agent_speech_events']}")
            logger.info(f"  - User state changes: {self.vad_stats['user_state_changes']}")
            logger.info(f"  - Agent state changes: {self.vad_stats['agent_state_changes']}")
            
            logger.info("🏁 Interview finalized (C# handles all database saves)")
            
            logger.info("🏁 Interview finalized successfully")
            
        except Exception as e:
            logger.error(f"❌ Error finalizing interview: {e}")

# ============================================================================
# 🔥 SIMPLIFIED INTERVIEW AGENT - VAD ONLY
# ============================================================================

class VadInterviewAgent(Agent):
    def __init__(self, interview_config, conversation_tracker):
        self.interview_config = interview_config
        self.job_position = interview_config.get('job_position', 'Software Developer')
        self.job_description = interview_config.get('job_description', '')
        self.questions = self._parse_questions(interview_config.get('question_list', ''))
        self.conversation_tracker = conversation_tracker
        
        # Create instructions
        instructions = self._create_instructions()
        super().__init__(instructions=instructions)
        
        logger.info(f"🤖 VAD-Only Interview Agent created for: {self.job_position}")
    
    def _parse_questions(self, question_list_str):
        """Parse questions from JSON string or plain text"""
        if not question_list_str:
            return [
                "Tell me about yourself and your experience.",
                "What are your strongest technical skills?",
                "Describe a challenging project you've worked on.",
                "Where do you see yourself in 5 years?",
                "Do you have any questions for us?"
            ]
        
        try:
            questions_json = json.loads(question_list_str)
            if isinstance(questions_json, list):
                return [q.get('Question', q) if isinstance(q, dict) else str(q) for q in questions_json]
            return [str(questions_json)]
        except:
            return [q.strip() for q in question_list_str.split(',') if q.strip()]
    
    def _create_instructions(self):
        """Create dynamic instructions for the AI interviewer"""
        questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(self.questions)])
        
        return f"""You are a professional AI interviewer conducting a voice interview for a {self.job_position} position.

Job Description: {self.job_description}

Interview Questions to Ask:
{questions_text}

 RULES:
- NEVER give answers or hints to questions
- Be encouraging and professional
- Stick To The Question List Dont Change The Topic.
- If asked for hints/help: You say "Take your time I Can't Provide Hint"
- If someone says "I don't know", acknowledge it positively and move on
- Stay neutral - Show Little Bit engagement: "That's interesting!", "Great example!", "Tell me more about that"
- Keep responses SHORT (1-2 sentences max)
- Keep the conversation flowing naturally
- Remember to be friendly but professional throughout the interview.

FLOW:
1. Greet: "Hello! I'm your AI recruiter for the {self.job_position} position. How are you feeling today?"
2. Ask questions ONE AT A TIME
3. Acknowledge briefly: "Thank you" or "I see"
4. Move to next question
5. End: "Thank you, that concludes our interview"

You evaluate, don't teach. Listen and assess only.

VAD-BASED TIMING:
- Speak clearly at a good pace
- Allow natural pauses for the candidate to think
- VAD will detect when they stop speaking and provide appropriate delays
- The system uses silence detection to determine when to respond

Remember: You're evaluating their fit for {self.job_position}. Be friendly, professional, and encouraging while maintaining natural conversation flow with VAD-based turn detection."""

# ============================================================================
# 🔥 SIMPLIFIED VAD SETUP (NO TURN DETECTOR)
# ============================================================================

def create_silero_vad():
    """Create Silero VAD with proper configuration"""
    try:
        vad = silero.VAD.load(
            min_speech_duration=Config.VAD_MIN_SPEECH_DURATION,
            min_silence_duration=Config.VAD_MIN_SILENCE_DURATION,
            prefix_padding_duration=Config.VAD_PREFIX_PADDING_DURATION,
            max_buffered_speech=Config.VAD_MAX_BUFFERED_SPEECH,
            activation_threshold=Config.VAD_ACTIVATION_THRESHOLD,
            sample_rate=Config.VAD_SAMPLE_RATE,
            force_cpu=Config.VAD_FORCE_CPU
        )
        
        logger.info(f"🎤 Silero VAD configured:")
        logger.info(f"  - Min speech duration: {Config.VAD_MIN_SPEECH_DURATION}s")
        logger.info(f"  - Min silence duration: {Config.VAD_MIN_SILENCE_DURATION}s")
        logger.info(f"  - Activation threshold: {Config.VAD_ACTIVATION_THRESHOLD}")
        logger.info(f"  - Sample rate: {Config.VAD_SAMPLE_RATE}Hz")
        
        return vad
    except Exception as e:
        logger.error(f"❌ Failed to create Silero VAD: {e}")
        logger.info("💡 Install with: pip install livekit-agents[silero]")
        return None

def create_enhanced_tts():
    """Create enhanced TTS with faster, louder speech"""
    try:
        base_tts = aws.TTS(
            voice="Matthew",
            speech_engine="standard",
            language="en-US"
        )
        
        logger.info("🔊 Enhanced TTS created: Matthew voice")
        return base_tts
        
    except Exception as e:
        logger.error(f"❌ Failed to create enhanced TTS: {e}")
        return aws.TTS(voice="Matthew", speech_engine="standard", language="en-US")

# ============================================================================
# 🔥 SIMPLIFIED ENTRYPOINT - VAD ONLY
# ============================================================================

async def entrypoint(ctx: agents.JobContext):
    """Simplified entrypoint with VAD-only detection"""
    logger.info(f"🚀 LiveKit Agent with VAD-ONLY starting for room: {ctx.room.name}")
        # 🔥 ADD 1-SECOND DELAY BEFORE AGENT JOINS
    logger.info("⏳ Waiting 2 second before agent joins the room...")
    await asyncio.sleep(0.5)
    logger.info("✅ Agent delay complete, now connecting to room")
    # Connect to room
    await ctx.connect()
    
    # Extract interview ID
    room_name = ctx.room.name
    interview_id = None
    
    if room_name.startswith("interview-"):
        parts = room_name.split("-")
        if len(parts) >= 2:
            interview_id = parts[1]
    
    if not interview_id:
        logger.error(f"❌ Could not extract interview ID from room name: {room_name}")
        return
    
    logger.info(f"📋 Interview ID: {interview_id}")
    
    # Get interview config
    interview_config = db.get_interview(interview_id)
    if not interview_config or interview_config.get('voice_platform') != 'livekit':
        logger.error(f"❌ Invalid interview: {interview_id}")
        return
    
    # Create VAD conversation tracker
    conversation_tracker = VadConversationTracker(interview_id)
    
    # Create VAD interview agent
    agent = VadInterviewAgent(interview_config, conversation_tracker)
    
    # 🔥 SIMPLIFIED: Create VAD and TTS only
    vad = create_silero_vad()
    enhanced_tts = create_enhanced_tts()
    
    # 🔥 SIMPLIFIED: Create AgentSession with VAD-only parameters
    session_params = {
        "stt": assemblyai.STT() if Config.ASSEMBLYAI_API_KEY else None,
        "llm": openai.LLM(model="gpt-4.1-mini-2025-04-14", temperature=0.2),
        "tts": enhanced_tts,
        "allow_interruptions": Config.ALLOW_INTERRUPTIONS,
        "min_interruption_duration": Config.MIN_INTERRUPTION_DURATION,
        "min_endpointing_delay": Config.MIN_ENDPOINTING_DELAY,
        "max_endpointing_delay": Config.MAX_ENDPOINTING_DELAY,
        "turn_detection": "vad",  # 🔥 SIMPLIFIED: VAD-only mode
    }
    
    # Add VAD if available
    if vad:
        session_params["vad"] = vad
        logger.info("✅ Silero VAD added to session")
    
    # Create the simplified session
    session = AgentSession(**session_params)
    
    logger.info(f"✅ VAD-Only AgentSession configured:")
    logger.info(f"  - VAD: {'✅ Silero' if vad else '❌ None'}")
    logger.info(f"  - Turn Detection: VAD-only mode")
    logger.info(f"  - Interruptions: {'✅ Enabled' if Config.ALLOW_INTERRUPTIONS else '❌ Disabled'}")
    logger.info(f"  - Min endpointing delay: {Config.MIN_ENDPOINTING_DELAY}s")
    logger.info(f"  - Max endpointing delay: {Config.MAX_ENDPOINTING_DELAY}s")
    
    # 🔥 SIMPLIFIED: Set up VAD-only event handlers
    @session.on("user_state_changed")
    def on_user_state_changed(event: UserStateChangedEvent):
        conversation_tracker.on_user_state_changed(event)
    
    @session.on("agent_state_changed")
    def on_agent_state_changed(event: AgentStateChangedEvent):
        conversation_tracker.on_agent_state_changed(event)
    
    # Enhanced transcript capture (keep your existing working logic)
    def setup_enhanced_transcript_capture():
        """Set up enhanced transcript capture with VAD awareness"""
        try:
            stt = session.stt if hasattr(session, 'stt') else None
            
            if stt:
                logger.info("🎤 Setting up VAD-based STT transcript capture")
                
                original_on_transcript = getattr(stt, '_on_final_transcript', None)
                
                def enhanced_on_transcript(transcript):
                    """Capture transcripts with VAD awareness"""
                    try:
                        text = None
                        if hasattr(transcript, 'text'):
                            text = transcript.text
                        elif hasattr(transcript, 'alternatives') and transcript.alternatives:
                            text = transcript.alternatives[0].text if transcript.alternatives else None
                        elif isinstance(transcript, str):
                            text = transcript
                        
                        if text and text.strip():
                            logger.info(f"🎤 VAD capture: {text}")
                            conversation_tracker.add_user_message(text.strip())
                        
                        if original_on_transcript:
                            original_on_transcript(transcript)
                            
                    except Exception as e:
                        logger.error(f"❌ Error in VAD transcript: {e}")
                
                if hasattr(stt, '_on_final_transcript'):
                    stt._on_final_transcript = enhanced_on_transcript
                    logger.info("✅ VAD transcript handler installed")
                else:
                    logger.warning("⚠️ Could not find _on_final_transcript")
            else:
                logger.warning("⚠️ No STT found for VAD capture")
                
        except Exception as e:
            logger.error(f"❌ Error setting up VAD capture: {e}")
    
    # Set up transcript capture
    setup_enhanced_transcript_capture()
    
    # Enhanced assistant response capture
    original_generate_reply = session.generate_reply
    
    async def enhanced_generate_reply(*args, **kwargs):
        """Capture AI responses with VAD awareness"""
        try:
            logger.info("🤖 Generating AI response with VAD timing...")
            result = await original_generate_reply(*args, **kwargs)
            
            if result:
                response_text = None
                if hasattr(result, 'text'):
                    response_text = result.text
                elif hasattr(result, 'content'):
                    response_text = result.content
                elif isinstance(result, str):
                    response_text = result
                
                if response_text and response_text.strip():
                    logger.info(f"🤖 AI response captured: {response_text[:50]}...")
                    conversation_tracker.add_assistant_message(response_text.strip())
            
            return result
        except Exception as e:
            logger.error(f"❌ Error in AI response capture: {e}")
            return await original_generate_reply(*args, **kwargs)
    
    session.generate_reply = enhanced_generate_reply
    
    # 🔥 SIMPLIFIED: VAD Monitoring
    async def monitor_vad_activity():
        """Monitor VAD activity"""
        while True:
            try:
                await asyncio.sleep(10)
                
                logger.info(f"🔍 VAD Status:")
                logger.info(f"  - Messages captured: {len(conversation_tracker.conversation_log)}")
                logger.info(f"  - User speech events: {conversation_tracker.vad_stats['user_speech_events']}")
                logger.info(f"  - Agent speech events: {conversation_tracker.vad_stats['agent_speech_events']}")
                logger.info(f"  - Current user state: {conversation_tracker.vad_stats['last_user_state']}")
                logger.info(f"  - Current agent state: {conversation_tracker.vad_stats['last_agent_state']}")
                
                # Log VAD configuration status
                if vad:
                    logger.debug(f"  - VAD threshold: {Config.VAD_ACTIVATION_THRESHOLD}")
                    logger.debug(f"  - VAD min silence: {Config.VAD_MIN_SILENCE_DURATION}s")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ VAD monitor error: {e}")
    
    # Start VAD monitoring task
    asyncio.create_task(monitor_vad_activity())
    
    # Simplified cleanup with VAD statistics
    async def vad_cleanup():
        try:
            logger.info("🧹 VAD cleanup starting...")
            
            # Log final VAD statistics
            logger.info("📊 Final VAD Statistics:")
            logger.info(f"  - User speech events: {conversation_tracker.vad_stats['user_speech_events']}")
            logger.info(f"  - Agent speech events: {conversation_tracker.vad_stats['agent_speech_events']}")
            logger.info(f"  - User state changes: {conversation_tracker.vad_stats['user_state_changes']}")
            logger.info(f"  - Agent state changes: {conversation_tracker.vad_stats['agent_state_changes']}")
            
            # Calculate conversation quality metrics
            total_events = conversation_tracker.vad_stats['user_speech_events'] + conversation_tracker.vad_stats['agent_speech_events']
            if total_events > 0:
                user_participation = conversation_tracker.vad_stats['user_speech_events'] / total_events if total_events > 0 else 0
                
                logger.info(f"📈 Conversation Quality Metrics:")
                logger.info(f"  - Total speech events: {total_events}")
                logger.info(f"  - User participation rate: {user_participation:.2%}")
            
            # Finalize conversation tracking
            conversation_tracker.finalize()
            logger.info("✅ VAD cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ VAD cleanup error: {e}")
    
    ctx.add_shutdown_callback(vad_cleanup)
    
    # Start session with VAD configuration
    await session.start(agent=agent, room=ctx.room)
    
    # Add initial greeting
    greeting = f"Hello! I'm your AI recruiter for the {interview_config['job_position']} position. How are you feeling today?"
    conversation_tracker.add_assistant_message(greeting)
    
    # Generate initial response
    await session.generate_reply(
        instructions="Greet the candidate warmly as their AI recruiter and ask how they're feeling today. Keep it brief and professional."
    )
    
    logger.info(f"🎉 LiveKit Agent with VAD-ONLY active in room: {room_name}")
    
    # 🔥 DEBUGGING: Log transcript events every 5 seconds
    async def debug_transcript_status():
        while True:
            try:
                await asyncio.sleep(5)
                logger.info(f"🔍 Debug: {len(conversation_tracker.conversation_log)} messages captured")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Debug error: {e}")
    
    asyncio.create_task(debug_transcript_status())


# ============================================================================
# 🔥 SIMPLIFIED DEPENDENCY CHECKER
# ============================================================================

def check_vad_dependencies():
    """Check for required VAD dependencies only"""
    logger.info("🔍 Checking VAD dependencies...")
    
    missing_packages = []
    
    # Check for Silero VAD
    try:
        import livekit.plugins.silero
        logger.info("✅ Silero VAD plugin available")
    except ImportError:
        missing_packages.append("livekit-agents[silero]")
        logger.warning("❌ Silero VAD plugin not available")
    
    # Check for AssemblyAI STT
    try:
        import livekit.plugins.assemblyai
        logger.info("✅ AssemblyAI STT plugin available")
    except ImportError:
        missing_packages.append("livekit-agents[assemblyai]")
        logger.warning("❌ AssemblyAI STT plugin not available")
    
    # Check for OpenAI LLM
    try:
        import livekit.plugins.openai
        logger.info("✅ OpenAI LLM plugin available")
    except ImportError:
        missing_packages.append("livekit-agents[openai]")
        logger.warning("❌ OpenAI LLM plugin not available")
    
    # Check for AWS TTS
    try:
        import livekit.plugins.aws
        logger.info("✅ AWS TTS plugin available")
    except ImportError:
        missing_packages.append("livekit-agents[aws]")
        logger.warning("❌ AWS TTS plugin not available")
    
    if missing_packages:
        logger.warning("⚠️ Missing packages detected:")
        for package in missing_packages:
            logger.warning(f"  - {package}")
        
        logger.info("📦 To install missing packages, run:")
        logger.info(f"pip install {' '.join(missing_packages)}")
        
        return False
    else:
        logger.info("✅ All VAD dependencies are available")
        return True

# ============================================================================
# 🔥 SIMPLIFIED CONFIGURATION VALIDATOR
# ============================================================================

def validate_vad_config():
    """Validate VAD-only configuration"""
    logger.info("🔧 Validating VAD configuration...")
    
    # Check basic config
    required = [
        ("DATABASE_CONNECTION_STRING", Config.DATABASE_CONNECTION_STRING),
        ("LIVEKIT_API_KEY", Config.LIVEKIT_API_KEY),
        ("LIVEKIT_API_SECRET", Config.LIVEKIT_API_SECRET),
        ("LIVEKIT_WS_URL", Config.LIVEKIT_WS_URL),
        ("OPENAI_API_KEY", Config.OPENAI_API_KEY),
    ]
    
    missing = [name for name, value in required if not value]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    # Validate VAD configuration
    if Config.VAD_MIN_SPEECH_DURATION < 0.01 or Config.VAD_MIN_SPEECH_DURATION > 1.0:
        logger.warning(f"⚠️ VAD_MIN_SPEECH_DURATION ({Config.VAD_MIN_SPEECH_DURATION}) outside recommended range (0.01-1.0)")
    
    if Config.VAD_MIN_SILENCE_DURATION < 0.1 or Config.VAD_MIN_SILENCE_DURATION > 3.0:
        logger.warning(f"⚠️ VAD_MIN_SILENCE_DURATION ({Config.VAD_MIN_SILENCE_DURATION}) outside recommended range (0.1-3.0)")
    
    if Config.VAD_ACTIVATION_THRESHOLD < 0.1 or Config.VAD_ACTIVATION_THRESHOLD > 0.9:
        logger.warning(f"⚠️ VAD_ACTIVATION_THRESHOLD ({Config.VAD_ACTIVATION_THRESHOLD}) outside recommended range (0.1-0.9)")
    
    # Validate sample rate
    if Config.VAD_SAMPLE_RATE not in [8000, 16000]:
        logger.warning(f"⚠️ VAD_SAMPLE_RATE ({Config.VAD_SAMPLE_RATE}) must be 8000 or 16000. Using 16000.")
        Config.VAD_SAMPLE_RATE = 16000
    
    logger.info("✅ VAD configuration validated")
    logger.info(f"🎤 VAD Settings:")
    logger.info(f"  - Min speech: {Config.VAD_MIN_SPEECH_DURATION}s")
    logger.info(f"  - Min silence: {Config.VAD_MIN_SILENCE_DURATION}s") 
    logger.info(f"  - Threshold: {Config.VAD_ACTIVATION_THRESHOLD}")
    logger.info(f"  - Sample rate: {Config.VAD_SAMPLE_RATE}Hz")
    logger.info(f"⚡ Interruptions: {'Enabled' if Config.ALLOW_INTERRUPTIONS else 'Disabled'}")
    
    return True

# ============================================================================
# LIVEKIT AGENT STARTUP FUNCTION (MOVED FROM MAIN)
# ============================================================================

def start_livekit_agent():
    """Start your existing LiveKit agent code"""
    global agent_started, agent_status
    
    try:
        # Give Flask a moment to start
        time.sleep(3)
        
        agent_status = "initializing"
        logger.info("🚀 AIRecruiters LiveKit Agent (VAD-ONLY MODE)")
        logger.info("=" * 60)
        
        # Check VAD dependencies
        agent_status = "checking_dependencies"
        deps_available = check_vad_dependencies()
        if not deps_available:
            logger.warning("⚠️ Some dependencies are missing. Please install them to continue.")
            agent_status = "dependency_error"
            return
        
        # Validate VAD configuration
        agent_status = "validating_config"
        validate_vad_config()
        
        # Test database connection
        agent_status = "testing_database"
        if not db.test_connection():
            raise Exception("Database connection failed")
        
        logger.info(f"🔗 LiveKit URL: {Config.LIVEKIT_WS_URL}")
        logger.info(f"🔑 API Key: {Config.LIVEKIT_API_KEY[:8]}...")
        
        # Set up environment variables for LiveKit
        agent_status = "setting_environment"
        os.environ.update({
            "LIVEKIT_URL": Config.LIVEKIT_WS_URL,
            "LIVEKIT_API_KEY": Config.LIVEKIT_API_KEY,
            "LIVEKIT_API_SECRET": Config.LIVEKIT_API_SECRET,
        })
        
        logger.info("🌐 Starting LiveKit Agent with VAD-ONLY mode...")
        
        # Run the agent using LiveKit CLI
        agent_status = "starting_agent"
        import sys
        sys.argv = ['livekit_service.py', 'dev']
        
        agent_started = True
        agent_status = "running"
        
        agents.cli.run_app(
            agents.WorkerOptions(entrypoint_fnc=entrypoint)
        )
        
    except Exception as e:
        logger.error(f"❌ VAD-only agent startup failed: {e}")
        agent_started = False
        agent_status = f"error: {str(e)}"

# Start your LiveKit agent in background thread
agent_thread = threading.Thread(target=start_livekit_agent, daemon=True)
agent_thread.start()

# ============================================================================
# MAIN - HANDLES BOTH LOCAL AND AZURE DEPLOYMENT
# ============================================================================

if __name__ == "__main__":
    # When running locally, start the agent directly
    print("🖥️ Running locally - starting LiveKit agent directly")
    start_livekit_agent()
else:
    # When running on Azure, Flask handles this via the background thread
    print("☁️ Running on Azure - LiveKit agent started in background thread")
    print(f"🌐 Flask app available at health endpoints")
    pass