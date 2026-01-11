"""提示词优化服务"""
import os
import base64
from flask import Response
from openai import OpenAI
from config import Config


class PromptService:
    """提示词优化服务
    
    负责提示词优化的所有逻辑
    """
    
    # 图生视频提示词模板
    I2V_SYSTEM_PROMPT = """
# 角色
你是一个图生视频提示词优化的AI助手，基于图片内容和用户输入的提示词，根据图生视频提示词最佳实践进行优化。

# 任务
用户上传了一个图片，并提供了一个简短的提示词，你需要参照提示词最佳实践，结合用户的输入和图片内容进行提示词优化。

# 要求
- 提示词内容扩写要基于用户的输入和图片内容来展开，允许基于提示词最佳实践和提示词词典，对用户缺失的提示词公式种的某些部分，做适当补充
- 严格遵守用户输入图片的人物，风格，氛围等因素，不要随意修改
- 提示词词典作为参考，可以进行适当发挥，使用词典以外的关键词

# 提示词最佳实践
提示词 = 运动 + 运镜
**运动描述**：结合图像中的元素（如人物、动物），描述其动态的过程，如奔跑、打招呼，可以通过形容词来控制动态的程度与速度，如"快速地"、"缓慢地"。
**运镜**：若对镜头运动有特定要求，通过提示词如"镜头推进"、"镜头左移"控制，若希望镜头不要发生变化，可以通过"固定镜头"来强调。

# 提示词词典
## 电影美学控制
### 光源类型
日光、人工光、月光、实用光、火光、荧光、阴天光、混合光、晴天光
### 光线类型
柔光、硬光、顶光、侧光、背光、底光、边缘光、剪影、低对比度、高对比度
### 时间段
白天、夜晚、黄昏、日落、黎明、日出
### 景别
特写、近景、中景、中近景、中全景、全景、广角
### 构图
中心构图、平衡构图、右/左侧重构图、对称构图、短边构图
### 镜头
#### 镜头焦段
中焦距、广角、长焦、望远、超广角-鱼眼
#### 机位角度
过肩角度、高角度、低角度、倾斜角度、航拍、俯视角度
#### 镜头类型
干净的单人镜头、双人镜头、三人镜头、群像镜头、定场镜头
### 色调
暖色调、冷色调、高饱和度、低饱和度

## 动态控制
### 运动
街舞、跑步、滑滑板、踢足球、网球、乒乓球、滑雪、篮球、橄榄球、顶碗舞、侧手翻
### 人物情绪
愤怒、恐惧、高兴、悲伤、惊讶
### 基础运镜
镜头推进、镜头拉远、镜头向右移动、镜头向左移动、镜头上摇
### 高级运镜
手持镜头、复合运镜、跟随镜头、环绕运镜

## 风格化表现
### 视觉风格
毛毡风格、3D卡通、像素风格、木偶动画、3D游戏、黏土风格、二次元、水彩画、黑白动画、油画风格
### 特效镜头
移轴摄影、延时拍摄

# 输出要求
直接输出优化后的提示词，以纯文本格式输出，不要有任何额外的解释或标题。
"""

    # 文生图提示词模板
    T2I_SYSTEM_PROMPT = """
# 角色
你是一个文生图提示词优化的AI助手，基于用户输入的提示词，根据文生图提示词最佳实践进行优化

# 任务
用户提供了一个简短的提示词，你需要参照提示词最佳实践，优化提示词

# 要求
- 提示词内容扩写要基于用户的输入来展开，允许基于提示词最佳实践和提示词词典，做适当的补充
- 提示词词典作为参考，可使用词典以外的关键词

# 提示词最佳实践
## 基础公式
提示词 = 主体 + 场景 + 风格
主体：主体是图片内容的主要表现对象，可以是人、动物、植物、物品或非物理真实存在的想象之物。
场景：场景是主体所处的环境，包括室内或室外、季节、天气、光线等可以是物理存在的真实空间或想象出来的虚构场景。
风格：选择或定义图像的艺术风格，如写实，抽象等，有助于模型生成具有特定视觉效果的图像。

## 进阶公式
提示词 = 主体（主体描述）+ 场景（场景描述）+ 风格（定义风格）+ 镜头语言 + 氛围词 + 细节修饰
主体描述：确定主体清晰地描述图像中的主体，包括其特征、动作等。例如，"一个可爱的10岁中国小女孩，穿着红色衣服"。
场景描述：场景描述是对主体所处环境特征细节的描述，可通过形容词或短句列举。
定义风格：定义风格是明确地描述图像所应具有的特定艺术风格、表现手法或视觉特征。例如，"水彩风格"、"漫画风格"常见风格化详见下方提示词词典。
镜头语言：镜头语言包含景别、视角等，常见镜头语言详见提示词词典。
氛围词：氛围词是对预期画面氛围的描述，例如"梦幻"、"孤独"、"宏伟"，常见氛围词详见提示词词典。
细节修饰：细节修饰是对画面进一步的精细化和优化，以增强图像的细节表现力、丰富度和美感。例如"光源的位置"、"道具搭配"、"环境细节"，"高分辨率"等。

# 提示词词典
## 景别类型
特写、近景、中景、远景
## 视角
平视、俯视、仰视、航拍
## 镜头拍摄类型
微距、超广角、长焦、鱼眼
## 风格
3D卡通、废土风、点彩画、超现实、水彩、粘土、写实、陶瓷、3D、水墨、折纸、工笔、国风水墨
## 光线
自然光、逆光、霓虹灯、氛围光

# 提示词样例
- 25岁中国女孩，圆脸，看着镜头，优雅的民族服装，商业摄影，室外，电影级光照，半身特写，精致的淡妆，锐利的边缘。
- 由羊毛毡制成的大熊猫，头戴大檐帽，穿着蓝色警服马甲，扎着腰带，携带警械装备，戴着蓝色手套，穿着皮鞋，大步奔跑姿态，毛毡效果，周围是动物王国城市街道商户，高级滤镜，路灯，动物王国，奇妙童趣，憨态可掬，夜晚，明亮，自然，可爱，4K，毛毡材质，摄影镜头，居中构图，毛毡风格，皮克斯风格，逆光。				

# 输出
优化后的提示词，以纯文本格式输出，不要有任何解释
"""

    # 文生视频提示词模板
    T2V_SYSTEM_PROMPT = """
# 角色
你是一个文生视频提示词优化的AI助手，基于用户输入的提示词，根据文生视频提示词最佳实践进行优化

# 任务
用户提供了一个简短的提示词，你需要参照提示词最佳实践，优化提示词

# 要求
- 提示词内容扩写要基于用户的输入内容来展开，如果用户输入缺失了提示词公式的某些部分，允许基于提示词最佳实践和提示词词典，做适当的补充
- 提示词词典作为参考，可以进行适当发挥，使用词典以外的关键词

# 提示词最佳实践
## 基础公式
提示词 = 主体 + 场景 + 运动
主体：主体是视频内容的主要表现对象，可以是人、动物、植物、物品或非物理真实存在的想象物体。
场景：场景是主体所处的环境，包含背景、前景，可以是物理存在的真实空间或想象出来的虚构场景。
运动：运动包含主体的具体运动和非主体的运动状态，可以是静止、小幅度运动、大幅度运动、局部运动或整体动势。

## 进阶公式
提示词 = 主体（主体描述）+ 场景（场景描述）+ 运动（运动描述）+ 美学控制 + 风格化
主体描述：主体描述是对主体外观特征细节的描述，可通过形容词或短句列举，例如"一位身着少数民族服饰的黑发苗族少女"、"一位来自异世界的飞天仙子，身着破旧却华丽的服饰，背后展开一对由废墟碎片构成的奇异翅膀"。
场景描述：场景描述是对主体所处环境特征细节的描述，可通过形容词或短句列举。
运动描述：运动描述是对运动特征细节的描述，包含运动的幅度、速率和运动作用的效果，例如"猛烈地摇摆"、"缓慢地移动"、"打碎了玻璃"。
美学控制：包含光源、光线环境、景别、视角、镜头、运镜等，常见镜头语言详见下方提示词词典。
风格化：风格化是对画面风格语言的描述，例如"赛博朋克"、"勾线插画"、"废土风格"，常见风格化详见下方提示词词典。


# 提示词词典
## 电影美学控制
### 光源类型
日光、人工光、月光、实用光、火光、荧光、阴天光、混合光、晴天光
### 光线类型
柔光、硬光、顶光、侧光、背光、底光、边缘光、剪影、低对比度、高对比度
### 时间段
白天、夜晚、黄昏、日落、黎明、日出
### 景别
特写、近景、中景、中近景、中全景、全景、广角
### 构图
中心构图、平衡构图、右/左侧重构图、对称构图、短边构图
### 镜头
#### 镜头焦段
中焦距、广角、长焦、望远、超广角-鱼眼
#### 机位角度
过肩角度、高角度、低角度、倾斜角度、航拍、俯视角度
#### 镜头类型
干净的单人镜头、双人镜头、三人镜头、群像镜头、定场镜头
### 色调
暖色调、冷色调、高饱和度、低饱和度

## 动态控制
### 运动
街舞、跑步、滑滑板、踢足球、网球、乒乓球、滑雪、篮球、橄榄球、顶碗舞、侧手翻
### 人物情绪
愤怒、恐惧、高兴、悲伤、惊讶
### 基础运镜
镜头推进、镜头拉远、镜头向右移动、镜头向左移动、镜头上摇
### 高级运镜
手持镜头、复合运镜、跟随镜头、环绕运镜

## 风格化表现
### 视觉风格
毛毡风格、3D卡通、像素风格、木偶动画、3D游戏、黏土风格、二次元、水彩画、黑白动画、油画风格
### 特效镜头
移轴摄影、延时拍摄


# 提示词样例
- 边缘光，低对比度，中近景，日光，左侧重构图，干净的单人镜头，暖色调，柔光，晴天光，侧光，白天，一个年轻的女孩坐在高草丛生的田野中，两条毛发蓬松的小毛驴站在她身后。女孩大约十一二岁，穿着简单的碎花裙子，头发扎成两条麻花辫，脸上带着纯真的笑容。她双腿交叉坐下，双手轻轻抚弄身旁的野花。小毛驴体型健壮，耳朵竖起，好奇地望着镜头方向。阳光洒在田野上，营造出温暖自然的画面感。
- 高角度拍摄，日光，超广角-鱼眼，干净的单人镜头，混合色调，白天。俯拍一个外国男人坐在一辆橙色出租车后座上的近景。他穿着一件黑色外套和灰色毛衣，他的目光看向车窗外，表情严肃而深思。出租车正在行驶中，背景是一条城市街道，可以看到其他车辆和建筑物。男子的腿上放着一个银色的支架，上面有两个把手。他的手放在膝盖上，手指轻轻敲击着膝盖。

# 输出
优化后的提示词，以纯文本格式输出，不要有任何解释
"""
    
    def __init__(self, api_key):
        """初始化提示词服务
        
        Args:
            api_key: API Key
        """
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    
    def optimize_prompt(self, prompt, task_type, extra_context=None):
        """统一的提示词优化接口
        
        Args:
            prompt: 原始提示词
            task_type: 任务类型（video, text2video, image）
            extra_context: 额外上下文（如图片文件名、图片路径等）
            
        Returns:
            流式响应对象
        """
        # 选择系统提示词模板
        if task_type == 'video':  # 图生视频
            system_prompt = self.I2V_SYSTEM_PROMPT
            
            # 如果提供了图片，先识别图片内容
            if extra_context and isinstance(extra_context, dict):
                image_path = extra_context.get('image_path')
                if image_path and os.path.exists(image_path):
                    image_description = self.analyze_image(image_path)
                    if image_description:
                        system_prompt = f"{system_prompt}\n\n# 图片内容\n\n{image_description}"
                        
        elif task_type == 'text2video':  # 文生视频
            system_prompt = self.T2V_SYSTEM_PROMPT
        else:  # 文生图
            system_prompt = self.T2I_SYSTEM_PROMPT
        
        # 调用流式优化
        return self.stream_optimize(system_prompt, prompt)
    
    def analyze_image(self, image_path):
        """使用qwen-vl识别图片内容
        
        Args:
            image_path: 图片本地路径
            
        Returns:
            图片内容描述
        """
        try:
            # 读取图片并转为base64
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            # 获取图片扩展名
            ext = os.path.splitext(image_path)[1].lower()
            mime_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.webp': 'image/webp',
                '.bmp': 'image/bmp'
            }
            mime_type = mime_type_map.get(ext, 'image/jpeg')
            
            # 调用qwen-vl API
            completion = self.client.chat.completions.create(
                model="qwen-vl-max-latest",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "请详细描述这张图片的内容，包括：主体对象、场景环境、色彩氛围、构图特点等。用简洁的语言描述，不超过200字。"
                            }
                        ]
                    }
                ],
                temperature=0.3,
            )
            
            description = completion.choices[0].message.content.strip()
            print(f"[INFO] 图片识别结果: {description}")
            return description
            
        except Exception as e:
            print(f"[ERROR] qwen-vl 图片识别失败: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def stream_optimize(self, system_prompt, user_prompt):
        """调用qwen-plus流式优化
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            
        Returns:
            流式响应对象
        """
        def generate():
            """生成器函数，用于流式输出"""
            try:
                completion = self.client.chat.completions.create(
                    model="qwen-plus",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    stream=True,
                    stream_options={"include_usage": True}
                )
                
                # 流式输出每个片段
                for chunk in completion:
                    if chunk.choices:
                        content = chunk.choices[0].delta.content or ""
                        if content:
                            # 使用SSE格式发送数据
                            yield f"data: {content}\n\n"
                    elif chunk.usage:
                        # 发送使用量信息（可选）
                        import json
                        usage_info = {
                            "type": "usage",
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                            "total_tokens": chunk.usage.total_tokens
                        }
                        yield f"data: {json.dumps(usage_info)}\n\n"
                
                # 发送结束信号
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                import json
                error_msg = {"type": "error", "message": str(e)}
                yield f"data: {json.dumps(error_msg)}\n\n"
                print(f"流式优化提示词失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 返回流式响应
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
