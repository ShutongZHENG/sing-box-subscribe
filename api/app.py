from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from urllib.parse import quote, unquote
import json
import os
import sys
import subprocess
import tempfile

# ==========================================
# 关键路径配置 (适配 Vercel 环境)
# ==========================================
# 获取当前文件 (api/app.py) 的目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (即 api 的上一级，包含 main.py 和 templates 的地方)
BASE_DIR = os.path.dirname(CURRENT_DIR)

# 初始化 Flask，明确告诉它模板文件夹在根目录下
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.secret_key = 'sing-box'

# 初始化环境变量
DEFAULT_JSON_STR = '{"subscribes":[{"url":"URL","tag":"tag_1","enabled":true,"emoji":1,"subgroup":"","prefix":"","User-Agent":"v2rayng"},{"url":"URL","tag":"tag_2","enabled":false,"emoji":0,"subgroup":"命名/named","prefix":"❤️","User-Agent":"clashmeta"}],"auto_set_outbounds_dns":{"proxy":"","direct":""},"save_config_path":"./config.json","auto_backup":false,"exclude_protocol":"ssr","config_template":"","Only-nodes":false}'
os.environ['TEMP_JSON_DATA'] = DEFAULT_JSON_STR

# 获取临时目录 (用于写入文件，Vercel 根目录不可写)
TEMP_DIR = tempfile.gettempdir()

def get_temp_json_data():
    data = os.environ.get('TEMP_JSON_DATA')
    return json.loads(data) if data else {}

# 读取 config_template (从根目录读)
def get_template_list():
    template_list = []
    # 使用 BASE_DIR 拼接路径
    config_template_dir = os.path.join(BASE_DIR, 'config_template')
    if os.path.exists(config_template_dir):
        template_files = os.listdir(config_template_dir)
        template_list = [os.path.splitext(f)[0] for f in template_files if f.endswith('.json')]
        template_list.sort()
    return template_list

# 读取 providers.json (从根目录读)
def read_providers_json():
    # 使用 BASE_DIR 拼接路径
    providers_path = os.path.join(BASE_DIR, 'providers.json')
    if os.path.exists(providers_path):
        with open(providers_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# 写入 providers.json (写入临时目录，防止报错 500)
def write_providers_json(data):
    # Vercel 根目录只读，所以我们只能写到 /tmp 下避免程序崩溃
    # 注意：这里的更改是暂时的，无法持久保存
    temp_path = os.path.join(TEMP_DIR, 'providers.json')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Write failed: {e}")

@app.route('/')
def index():
    return render_template('index.html', 
                           template_options=[f"{i+1}、{t}" for i, t in enumerate(get_template_list())], 
                           providers_data=json.dumps(read_providers_json(), indent=4, ensure_ascii=False), 
                           temp_json_data=json.dumps(get_temp_json_data(), indent=4, ensure_ascii=False))

@app.route('/update_providers', methods=['POST'])
def update_providers():
    try:
        data = json.loads(request.form.get('providers_data'))
        write_providers_json(data)
        flash('更新成功 (Vercel 环境下为临时生效)', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('index'))

@app.route('/edit_temp_json', methods=['POST'])
def edit_temp_json():
    try:
        new_data = request.form.get('temp_json_data')
        if new_data:
            # 校验一下 JSON 格式
            json_obj = json.loads(new_data)
            os.environ['TEMP_JSON_DATA'] = json.dumps(json_obj, indent=4, ensure_ascii=False)
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Empty data'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/config/<path:url>')
def config(url):
    # 你的核心逻辑：调用根目录的 main.py
    try:
        # 这里简化了参数提取，你可以把你的原始解析逻辑放回来
        # 关键是 subprocess 的调用方式
        
        main_py_path = os.path.join(BASE_DIR, 'main.py')
        
        # 准备环境变量，确保 main.py 能找到 parsers 模块
        env = os.environ.copy()
        env['PYTHONPATH'] = BASE_DIR
        
        # 修改 save_config_path 为 /tmp，防止 main.py 写入只读目录报错
        # 这一步很关键！我们需要 hack 一下传入的数据
        temp_data_obj = get_temp_json_data()
        # 强制将保存路径改为 /tmp/config.json
        temp_data_obj['save_config_path'] = os.path.join(TEMP_DIR, 'config.json')
        temp_data_str = json.dumps(temp_data_obj)

        file_param = request.args.get('file', '')
        tpl_index = str(int(file_param) - 1) if file_param.isdigit() else '0'

        # 调用 main.py
        subprocess.check_call(
            [sys.executable, main_py_path, '--template_index', tpl_index, '--temp_json_data', temp_data_str],
            cwd=BASE_DIR, # 必须在根目录执行
            env=env
        )
        
        # 读取生成的文件
        with open(os.path.join(TEMP_DIR, 'config.json'), 'r', encoding='utf-8') as f:
            return Response(f.read(), content_type='text/plain; charset=utf-8')

    except Exception as e:
        return Response(f"Error: {str(e)}", status=500)

@app.route('/generate_config', methods=['POST'])
def generate_config():
    # 逻辑同上，记得也要修改 save_config_path 指向 /tmp
    return redirect(url_for('index'))

@app.route('/clear_temp_json_data', methods=['POST'])
def clear_temp_json_data():
    os.environ['TEMP_JSON_DATA'] = '{}'
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)
