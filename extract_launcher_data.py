import sqlite3
import re
import os

def create_dummy_db(db_file):
    """
    创建一个包含示例数据的虚拟数据库，如果该文件已存在则不进行任何操作。
    """
    if os.path.exists(db_file):
        print(f"数据库文件 '{db_file}' 已存在，将直接使用现有文件。")
        return

    print(f"正在创建虚拟数据库 '{db_file}' 用于演示...")
    # 模拟数据
    # 注意：为了简化，这里的 schema 和数据类型可能与原始数据库不完全一致，但足以满足提取逻辑的需要。
    data = [
        (1, 'com.miui.home:string/new_default_folder_title_tools', None, -100, 2, 0, 0, 1, 1, 2, -1, None, None, None, None, None, None, None, '14,13,8,1,6,6,9,17,30,24,26,23,33,20,22,28,15,27,21,35,32,26,25,28', 0, 0, 'com.miui.home:string/new_default_folder_title_tools', None, -1, None),
        (6, '小米商城', '#Intent;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;launchFlags=0x10200000;component=com.xiaomi.shop/.activity.MainTabActivity;end', 327, -1, 4, 3, 1, 1, 0, -1, None, None, 'com.xiaomi.shop', None, None, None, None, '0,1,0,0,0,0,0,0,3,0,1,0,0,0,0,0,0,1,0,0,0,0,0,0', 0, 0, '小米商城', None, -1, None),
        (7, '小米视频', '#Intent;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;launchFlags=0x10200000;component=com.miui.video/.Launcher1;end', 325, -1, 6, 0, 1, 1, 0, -1, None, None, 'com.miui.video', None, None, None, None, '0,0,0,0,0,0,0,0,0,0,2,0,0,0,1,0,0,0,0,0,0,0,0,1', 0, 0, '小米视频', None, -1, None)
    ]

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        # 创建一个与问题描述类似的表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            _id INTEGER PRIMARY KEY,
            title TEXT,
            intent TEXT,
            container INTEGER,
            screen INTEGER,
            cellX INTEGER,
            cellY INTEGER,
            spanX INTEGER,
            spanY INTEGER,
            itemType INTEGER,
            appWidgetId INTEGER,
            isShortcut INTEGER,
            iconType INTEGER,
            iconPackage TEXT,
            iconResource TEXT,
            icon BLOB,
            uri TEXT,
            displayMode INTEGER,
            launchCount TEXT,
            sortMode INTEGER,
            itemFlags INTEGER,
            profileId TEXT,
            label TEXT,
            appWidgetProvider TEXT,
            originWidgetId INTEGER,
            product_id TEXT
        )
        ''')
        # 插入数据
        cursor.executemany('INSERT INTO favorites VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', data)
        conn.commit()
    except sqlite3.Error as e:
        print(f"创建数据库时出错: {e}")
    finally:
        if conn:
            conn.close()


def extract_package_info(db_file):
    """
    从指定的数据库文件中提取应用名和包名。
    """
    if not os.path.exists(db_file):
        print(f"错误: 数据库文件 '{db_file}' 不存在。")
        return

    results = []
    try:
        # 连接到 SQLite 数据库
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # 执行查询，选择 title 和 intent 字段
        cursor.execute("SELECT title, intent FROM favorites")
        rows = cursor.fetchall()

        # 编译正则表达式以提高效率
        # 匹配 "component=" 后面，"/" 前面的部分
        # ([^/]+) 是一个捕获组，匹配一个或多个非斜杠字符
        pattern = re.compile(r'component=([^/]+)/')

        print("\n提取结果:")
        print("-" * 20)
        
        for row in rows:
            app_name, intent_str = row

            # 过滤 intent 为空的行
            if not intent_str:
                continue
            
            # 在 intent 字符串中搜索匹配项
            match = pattern.search(intent_str)
            
            if match:
                # 提取第一个捕获组，即包名
                package_name = match.group(1)
                # 打印结果
                print(f"{package_name},{app_name}")


    except sqlite3.Error as e:
        print(f"数据库操作失败: {e}")
    finally:
        # 关闭数据库连接
        if 'conn' in locals() and conn:
            conn.close()


if __name__ == "__main__":
    db_filename = "launcher4x7.db"
    
    # 步骤 1: 创建一个虚拟数据库（如果它不存在）
    create_dummy_db(db_filename)
    
    # 步骤 2: 从数据库中提取并打印信息
    extract_package_info(db_filename)
