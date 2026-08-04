"""
古玉鉴真 — SQLAlchemy ORM 模型 (边缘端 SQLite)
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime,
    ForeignKey, create_engine, CheckConstraint,
)
from sqlalchemy.orm import declarative_base, relationship, Session
import uuid

Base = declarative_base()


def gen_uuid() -> str:
    return str(uuid.uuid4())


class JadePiece(Base):
    """玉器（鉴定/标注单元）"""
    __tablename__ = 'jade_pieces'

    id = Column(String, primary_key=True, default=gen_uuid)
    label_code = Column(String, unique=True, nullable=False)
    login_number = Column(String, unique=True, nullable=False)

    # 详情字段
    product_name = Column(String)           # 品名
    material = Column(String)               # 材质
    dimensions = Column(Text)               # JSON: 尺寸
    source_type = Column(String)            # 来源类型
    source_detail = Column(String)          # 来源详情

    # 状态
    authenticity = Column(String, nullable=False)  # '真老' | '新仿'
    era = Column(String, nullable=False)
    era_code = Column(String, nullable=False)
    annotated_by = Column(String)
    annotation_confidence = Column(Integer)
    notes = Column(Text)

    # 审查追踪
    review_count = Column(Integer, default=0)      # 审查 + 标注次数合计
    review_status = Column(String, default='imported')
    last_reviewed_at = Column(String)

    # 训练图路径
    training_image = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    images = relationship('Image', back_populates='piece', cascade='all, delete-orphan')
    auth_results = relationship('AuthResult', back_populates='piece', cascade='all, delete-orphan')


class Image(Base):
    """玉器图片"""
    __tablename__ = 'images'

    id = Column(String, primary_key=True, default=gen_uuid)
    piece_id = Column(String, ForeignKey('jade_pieces.id'), nullable=False)
    file_path = Column(String, nullable=False)
    image_type = Column(String, nullable=False)  # 'macro' | 'micro'
    camera_angle = Column(String)
    width = Column(Integer)
    height = Column(Integer)
    file_size_bytes = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    piece = relationship('JadePiece', back_populates='images')


class AuthResult(Base):
    """AI 鉴定结果"""
    __tablename__ = 'authentication_results'

    id = Column(String, primary_key=True, default=gen_uuid)
    piece_id = Column(String, ForeignKey('jade_pieces.id'), nullable=False)
    label_code = Column(String, unique=True, nullable=False)
    model_version = Column(String, nullable=False)
    predicted_era = Column(String, nullable=False)
    era_code = Column(String, nullable=False)
    era_probabilities = Column(Text)  # JSON
    predicted_authenticity = Column(String, nullable=False)
    authenticity_confidence = Column(Float)
    macro_features_analyzed = Column(Integer)
    micro_features_analyzed = Column(Integer)
    inference_time_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    piece = relationship('JadePiece', back_populates='auth_results')


class ModelVersion(Base):
    """本地模型版本缓存"""
    __tablename__ = 'model_versions'

    version_id = Column(String, primary_key=True)
    onnx_path = Column(String, nullable=False)
    downloaded_at = Column(DateTime, default=datetime.utcnow)
    model_size_bytes = Column(Integer)
    checksum = Column(String)


def create_database(db_path: str = 'jade.db') -> Session:
    """创建 SQLite 数据库和表，返回 session。"""
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    return Session()
