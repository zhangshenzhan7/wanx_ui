"""语音复刻服务 - 封装 CosyVoice API"""
import os
import json
import requests
from datetime import datetime
from typing import Dict, Optional, List
import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer
from core.utils.logger import setup_logger

logger = setup_logger(__name__)

# API 端点
ENROLL_API = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"


class VoiceService:
    """语音复刻服务 - 封装阿里云 CosyVoice API
    
    功能：
    - 创建音色（语音复刻）
    - 查询音色状态
    - 列出已创建的音色
    - 删除音色
    - 使用复刻音色合成语音
    """
    
    DEFAULT_MODEL = "cosyvoice-v3-plus"
    
    def __init__(self, api_key: str):
        """初始化语音服务
        
        Args:
            api_key: DashScope API Key
        """
        self.api_key = api_key
        dashscope.api_key = api_key
        self.enrollment_service = VoiceEnrollmentService()
    
    def create_voice(self, audio_url: str, prefix: str, 
                     target_model: str = None) -> Optional[Dict]:
        """创建音色（异步任务）
        
        使用 HTTP 请求直接调用 API，支持 oss:// 格式的临时资源 URL
        
        Args:
            audio_url: 音频URL（支持 oss:// 或 http/https）
            prefix: 音色前缀（仅允许小写字母和数字，<10字符）
            target_model: 目标模型
            
        Returns:
            包含 voice_id 的任务信息，失败返回 None
        """
        try:
            model = target_model or self.DEFAULT_MODEL
            
            payload = {
                "model": "voice-enrollment",
                "input": {
                    "action": "create_voice",
                    "target_model": model,
                    "prefix": prefix,
                    "url": audio_url,
                },
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                # 关键：允许后端解析 oss:// 临时资源
                "X-DashScope-OssResourceResolve": "enable",
            }
            
            resp = requests.post(ENROLL_API, headers=headers, data=json.dumps(payload), timeout=60)
            resp.raise_for_status()
            data = resp.json()
            
            # 解析 voice_id（不同版本响应结构可能略有差异）
            voice_id = (
                data.get("output", {}).get("voice_id")
                or data.get("voice_id")
                or data.get("output", {}).get("voiceId")
            )
            
            if not voice_id:
                logger.error(f"未解析到 voice_id，响应：{data}")
                return None
            
            request_id = data.get("request_id", "")
            logger.info(f"Voice enrollment submitted. voice_id={voice_id}, request_id={request_id}")
            
            return {
                'voice_id': voice_id,
                'prefix': prefix,
                'target_model': model,
                'status': 'DEPLOYING',
                'request_id': request_id,
                'created_at': datetime.now().isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"创建音色请求失败: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"创建音色失败: {e}", exc_info=True)
            return None
    
    def query_voice_status(self, voice_id: str) -> Optional[Dict]:
        """查询音色状态
        
        Args:
            voice_id: 音色ID
            
        Returns:
            音色信息，包含 status 字段:
            - "OK": 音色就绪，可用于合成
            - "DEPLOYING": 处理中
            - "UNDEPLOYED": 处理失败
        """
        try:
            voice_info = self.enrollment_service.query_voice(voice_id=voice_id)
            logger.info(f"Voice status queried. voice_id={voice_id}, status={voice_info.get('status')}")
            return voice_info
        except Exception as e:
            logger.error(f"查询音色状态失败: {e}", exc_info=True)
            return None
    
    def list_voices(self, prefix: str = None, page_index: int = 0, 
                    page_size: int = 10) -> Optional[Dict]:
        """列出所有音色
        
        Args:
            prefix: 音色前缀过滤
            page_index: 页码（从0开始）
            page_size: 每页数量
            
        Returns:
            音色列表信息
        """
        try:
            result = self.enrollment_service.list_voices(
                prefix=prefix,
                page_index=page_index,
                page_size=page_size
            )
            return result
        except Exception as e:
            logger.error(f"列出音色失败: {e}", exc_info=True)
            return None
    
    def delete_voice(self, voice_id: str) -> bool:
        """删除音色
        
        Args:
            voice_id: 音色ID
            
        Returns:
            是否删除成功
        """
        try:
            self.enrollment_service.delete_voice(voice_id=voice_id)
            logger.info(f"音色已删除: {voice_id}")
            return True
        except Exception as e:
            logger.error(f"删除音色失败: {e}", exc_info=True)
            return False
    
    def synthesize_speech(self, voice_id: str, text: str, 
                          output_path: str, model: str = None,
                          volume: int = 50, speech_rate: float = 1.0,
                          pitch_rate: float = 1.0) -> Optional[str]:
        """使用复刻音色合成语音
        
        Args:
            voice_id: 音色ID
            text: 要合成的文本
            output_path: 输出文件路径（应为 .mp3）
            model: 模型名称
            volume: 音量 (0-100)，默认50
            speech_rate: 语速 (0.5-2.0)，默认1.0
            pitch_rate: 音高 (0.5-2.0)，默认1.0
            
        Returns:
            输出文件路径，失败返回 None
        """
        try:
            target_model = model or self.DEFAULT_MODEL
            
            synthesizer = SpeechSynthesizer(
                model=target_model,
                voice=voice_id,
                volume=volume,
                speech_rate=speech_rate,
                pitch_rate=pitch_rate
            )
            
            audio_data = synthesizer.call(text)
            request_id = synthesizer.get_last_request_id()
            
            if audio_data:
                with open(output_path, 'wb') as f:
                    f.write(audio_data)
                logger.info(f"语音合成成功: {output_path}, request_id={request_id}")
                return output_path
            
            logger.error(f"语音合成返回空数据: voice_id={voice_id}")
            return None
            
        except Exception as e:
            logger.error(f"语音合成失败: {e}", exc_info=True)
            return None

