# app_classifier.py

import os
import json
import numpy as np
from google import genai
from google.genai import types
from dotenv import load_dotenv
from sklearn.cluster import DBSCAN
import sqlite3
import re

# 新增：定义缓存文件的路径
CACHE_FILE = "app_tags_cache.json"

def extract_apps_from_db(db_file: str) -> list[dict]:
    """
    从指定的数据库文件中提取应用名和包名。
    如果数据库文件不存在，则直接引发 FileNotFoundError。

    :param db_file: SQLite 数据库文件的路径。
    :return: 一个包含应用信息的字典列表，例如 [{'name': '微信', 'package': 'com.tencent.mm'}]。
    :raises FileNotFoundError: 如果 db_file 不存在。
    :raises sqlite3.Error: 如果发生数据库相关错误。
    """
    if not os.path.exists(db_file):
        raise FileNotFoundError(f"错误: 数据库文件 '{db_file}' 不存在。")

    apps = []
    conn = None # 预先定义conn，确保finally块中可用
    try:
        # 连接到 SQLite 数据库
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # 执行查询，选择 title 和 intent 字段
        cursor.execute("SELECT title, intent FROM favorites")
        rows = cursor.fetchall()

        # 编译正则表达式以提高效率
        # 匹配 "component=" 后面，"/" 前面的部分
        pattern = re.compile(r'component=([^/]+)/')

        for row in rows:
            app_name, intent_str = row

            # 过滤 intent 为空的行或不含 component 的行
            if not intent_str or 'component=' not in intent_str:
                continue
            
            # 在 intent 字符串中搜索匹配项
            match = pattern.search(intent_str)
            
            if match:
                # 提取第一个捕获组，即包名
                package_name = match.group(1)
                apps.append({'name': app_name, 'package': package_name})
        
        print(f"成功从 '{db_file}' 中提取了 {len(apps)} 个应用信息。")
        return apps

    except sqlite3.Error as e:
        # 将底层数据库异常继续向上抛出，由调用者处理
        raise sqlite3.Error(f"数据库操作失败: {e}") from e
    finally:
        # 关闭数据库连接
        if conn:
            conn.close()


def load_cache() -> dict:
    """
    加载本地缓存文件。如果文件不存在或为空，返回空字典。
    """
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            # 修正点: 增加对空文件的判断，避免json.load抛出异常
            content = f.read()
            if not content:
                return {}
            return json.loads(content)
    except (IOError, json.JSONDecodeError) as e:
        print(f"警告：读取缓存文件 '{CACHE_FILE}' 失败: {e}。将使用一个空的缓存开始。")
        return {}

def save_cache(cache_data: dict):
    """
    将缓存数据保存到JSON文件。
    """
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=4, ensure_ascii=False)
        print(f"\n缓存已成功保存到 '{CACHE_FILE}'。")
    except IOError as e:
        print(f"错误：无法将缓存写入文件 '{CACHE_FILE}': {e}")


def setup_gemini():
    """
    从.env文件加载API密钥并配置Gemini。
    """
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("错误：未找到GOOGLE_API_KEY。请确保您的.env文件配置正确。")

    print("Gemini 环境配置成功。")

def get_app_description(client: genai.Client, app_name: str, package_name: str) -> str:
    """
    第一步：根据应用名和包名，使用LLM生成一系列功能标签。
    """
    print(f"  > [API 调用] 正在为 '{app_name}' 生成功能标签...")
    
    prompt = f"""
# 角色
你是一位资深的安卓应用分析专家，精通识别各类应用的核心功能并将其“特征化”。

# 任务与规则
你的任务是根据我提供的应用名称和包名，精准地分析其核心功能，并生成一系列标签。在执行任务时，你必须严格遵守以下全部规则：

1.  **内容**: 标签必须是概括应用核心功能的中文关键词或短语。
2.  **数量**: 返回 3 到 5 个最相关的标签。对于功能非常单一的应用，可以少于3个，但不要超过5个。
3.  **格式**: 所有标签必须使用英文逗号 (`,`) 分隔。例如："标签1,标签2,标签3"。
4.  **纯净度**: 绝对不要包含任何标签之外的解释、介绍、编号、列表符号或任何其他多余的文字。你的回答应该是可以直接被程序解析的纯粹的标签字符串。
5.  **语言**: 所有标签都应使用中文。

## 示例 (Few-shot Examples)
以下是你需要遵循的格式和质量标准的示例：

### 示例 1
- **输入**:
  - 应用名称: "微信"
  - 应用包名: "com.tencent.mm"
- **期望输出**:
社交,即时通讯,支付,小程序平台

### 示例 2
- **输入**:
  - 应用名称: "楽天市場"
  - 应用包名: "jp.co.rakuten.android"
- **期望输出**:
在线购物,电商平台,积分返点,生活服务

### 示例 3
- **输入**:
  - 应用名称: "原神"
  - 应用包名: "com.miHoYo.Yuanshen"
- **期望输出**:
开放世界,角色扮演,动作游戏,二次元

### 示例 4
- **输入**:
  - 应用名称: "メルカリ" (Mercari)
  - 应用包名: "jp.mercari.android"
- **期望输出**:
二手交易,跳蚤市场,C2C电商,在线支付


## 异常处理规则
如果根据输入的应用信息，你无法在互联网上找到可靠资料或无法判断其核心功能，请严格遵守以下规则：
- **不要猜测或编造**。
- 你的回答必须是且仅是以下的中文字符，不包含任何其他内容：
信息不足


# 任务开始
现在，请为以下应用生成标签：

- **应用名称**: "{app_name}"
- **应用包名**: "{package_name}"
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        tags = response.text.strip()
        if not tags:
            return "信息不足"
        return tags
    except Exception as e:
        print(f"    ! 调用LLM生成标签时出错: {e}")
        return "信息不足"

def get_embedding(client: genai.Client, text: str) -> list[float] | None:
    """
    第二步：将标签字符串通过Embedding模型转换为向量。
    """
    print(f"  > 正在为标签 \"{text[:20]}...\" 生成向量...")
    try:
        result = client.models.embed_content(
            model="text-embedding-004",
            contents=text
        )
        return result['embedding']
    except Exception as e:
        print(f"    ! 调用Embedding模型时出错: {e}")
        return None

def main():
    """
    主函数，编排整个流程。
    """
    try:
        setup_gemini()
    except ValueError as e:
        print(e)
        return

    # --- 步骤 1: 从数据库加载应用列表 ---
    db_filename = "launcher4x7.db" # 假设数据库文件名为 launcher.db
    try:
        apps_to_process = extract_apps_from_db(db_filename)
    except (FileNotFoundError, sqlite3.Error) as e:
        print(e)
        return

    if not apps_to_process:
        print("数据库中没有找到有效的应用信息，程序终止。")
        return
    
    # 初始化新的客户端
    client = genai.Client()
    
    print("\n--- 开始处理应用列表 ---")

    # 加载缓存
    app_tags_cache = load_cache()
    
    processed_apps = []
    app_vectors = []

    for app in apps_to_process:
        app_name = app['name']
        package_name = app['package']
        print(f"\n处理应用: {app_name} ({package_name})")

        tags = ""
        # --- 步骤 2: 检查缓存或生成标签 ---
        if package_name in app_tags_cache:
            # 缓存命中
            tags = app_tags_cache[package_name]
            print(f"  > [缓存命中] 从缓存加载标签。")
        else:
            # 缓存未命中，调用API
            tags = get_app_description(client, app_name, package_name)
            # 将新结果存入缓存字典
            app_tags_cache[package_name] = tags
            # 修改点：每次查询到新结果后，立即写入缓存
            save_cache(app_tags_cache)
        
        print(f"  <-- 获得的标签: {tags}")

        if tags == "信息不足":
            print("  ! 跳过此应用，因为它信息不足。")
            continue
        
        app['tags'] = tags

        # --- 步骤 3: 生成向量 ---
        vector = get_embedding(client, tags)
        if vector:
            processed_apps.append(app)
            app_vectors.append(vector)
            print("  <-- 成功生成向量。")

    if not app_vectors:
        print("\n错误：未能为任何应用生成向量，无法进行聚类。")
        # 因为缓存已在每次获取新标签后保存，此处无需再次保存。
        return
        
    print("\n--- 所有应用处理完毕，开始进行向量聚类 ---")

    # --- 步骤 4: 向量聚类 ---
    vector_matrix = np.array(app_vectors)
    
    # 注意：eps参数需要根据你的数据和标签风格进行微调。
    # 0.3-0.6 是一个常见的起始范围。min_samples=2 表示至少2个应用才能成组。
    print("使用DBSCAN算法进行聚类 (eps=0.4, min_samples=2, metric='cosine')...")
    dbscan = DBSCAN(eps=0.4, min_samples=2, metric='cosine')
    clusters = dbscan.fit_predict(vector_matrix)
    
    print("\n--- 聚类完成！最终分类结果 ---")
    
    final_groups = {}
    for i, app_info in enumerate(processed_apps):
        cluster_id = clusters[i]
        
        if cluster_id == -1:
            group_name = "独立应用/离群点"
        else:
            group_name = f"分组 {cluster_id}"
            
        if group_name not in final_groups:
            final_groups[group_name] = []
        
        final_groups[group_name].append(app_info['name'])

    print(json.dumps(final_groups, indent=4, ensure_ascii=False))
    # 修改点：移除此处的最终保存调用，因为它已在循环中执行。

if __name__ == "__main__":
    main()