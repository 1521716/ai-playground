<?php
/**
 * 高考志愿大学助手 - API
 * 提供大学真实生活信息查询服务
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST');

// 数据文件路径
$dataFile = __DIR__ . '/data.json';

// 读取数据
function loadData($file) {
    if (!file_exists($file)) {
        return ['notice' => '数据文件不存在', 'hot' => [], 'universities' => []];
    }
    $json = file_get_contents($file);
    return json_decode($json, true) ?: ['notice' => '数据解析失败', 'hot' => [], 'universities' => []];
}

// 保存数据
function saveData($file, $data) {
    $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    return file_put_contents($file, $json, LOCK_EX) !== false;
}

// 记录纠错到日志文件
function logCorrection($file, $oldName, $newName) {
    $log = date('Y-m-d H:i:s') . " | 旧名: {$oldName} | 新名: {$newName}\n";
    file_put_contents($file, $log, FILE_APPEND | LOCK_EX);
}

$data = loadData($dataFile);

// ========== GET 请求处理 ==========
if ($_SERVER['REQUEST_METHOD'] === 'GET') {

    // 首页数据
    if (isset($_GET['get_home'])) {
        echo json_encode([
            'notice' => $data['notice'],
            'hot' => $data['hot']
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }

    // 按学校名搜索
    if (isset($_GET['search'])) {
        $kw = trim($_GET['search']);
        $results = [];
        if ($kw !== '') {
            foreach ($data['universities'] as $u) {
                if (mb_stripos($u['name'], $kw) !== false) {
                    $results[] = ['school_name' => $u['name']];
                }
            }
        }
        echo json_encode($results, JSON_UNESCAPED_UNICODE);
        exit;
    }

    // 按条件（问答内容）搜索
    if (isset($_GET['search_q'])) {
        $kw = trim($_GET['search_q']);
        $results = [];
        if ($kw !== '') {
            foreach ($data['universities'] as $u) {
                foreach ($u['qa'] as $qa) {
                    if (mb_stripos($qa['q'], $kw) !== false) {
                        $results[] = [
                            'school_name' => $u['name'],
                            'q' => $qa['q'],
                            'a' => implode('；', array_slice($qa['a'], 0, 3))
                        ];
                        break; // 每所学校最多匹配一次
                    }
                }
            }
        }
        echo json_encode($results, JSON_UNESCAPED_UNICODE);
        exit;
    }

    // 获取学校详情
    if (isset($_GET['name'])) {
        $name = trim($_GET['name']);
        $found = null;
        foreach ($data['universities'] as &$u) {
            if ($u['name'] === $name) {
                // 增加浏览量
                if (!isset($u['views'])) {
                    $u['views'] = 1;
                } else {
                    $u['views']++;
                }
                // 同步更新热搜列表中的浏览量
                foreach ($data['hot'] as &$h) {
                    if ($h['school_name'] === $name) {
                        $h['views'] = (string)$u['views'];
                        break;
                    }
                }
                saveData($dataFile, $data);
                $found = $u;
                break;
            }
        }
        if ($found) {
            echo json_encode($found, JSON_UNESCAPED_UNICODE);
        } else {
            echo json_encode(['error' => '未找到该学校的信息'], JSON_UNESCAPED_UNICODE);
        }
        exit;
    }

    // 无参数时返回提示
    echo json_encode(['error' => '请提供有效的查询参数'], JSON_UNESCAPED_UNICODE);
    exit;
}

// ========== POST 请求处理 ==========
if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    // 用户提交补充内容
    if (isset($_POST['submit_content'])) {
        $schoolName = trim($_POST['school_name'] ?? '');
        $content = trim($_POST['user_content'] ?? '');

        if ($schoolName === '' || $content === '') {
            echo json_encode(['error' => '学校名称和补充内容不能为空'], JSON_UNESCAPED_UNICODE);
            exit;
        }

        if (mb_strlen($content) > 500) {
            echo json_encode(['error' => '内容不能超过500字'], JSON_UNESCAPED_UNICODE);
            exit;
        }

        $found = false;
        foreach ($data['universities'] as &$u) {
            if ($u['name'] === $schoolName) {
                if (!isset($u['user_replies'])) {
                    $u['user_replies'] = [];
                }
                $u['user_replies'][] = [
                    'user_content' => $content,
                    'time' => date('Y-m-d H:i:s')
                ];
                $found = true;
                break;
            }
        }

        if ($found) {
            if (saveData($dataFile, $data)) {
                echo json_encode(['status' => 'ok', 'msg' => '✅ 提交成功！感谢你的贡献，内容将在审核后显示。'], JSON_UNESCAPED_UNICODE);
            } else {
                echo json_encode(['error' => '保存失败，请稍后重试'], JSON_UNESCAPED_UNICODE);
            }
        } else {
            echo json_encode(['error' => '未找到该学校，请检查学校名称是否正确'], JSON_UNESCAPED_UNICODE);
        }
        exit;
    }

    // 校名纠错
    if (isset($_POST['report_error'])) {
        $oldName = trim($_POST['old_name'] ?? '');
        $newName = trim($_POST['new_name'] ?? '');

        if ($oldName === '' || $newName === '') {
            echo json_encode(['error' => '新旧校名不能为空'], JSON_UNESCAPED_UNICODE);
            exit;
        }

        // 记录到日志文件
        $logFile = __DIR__ . '/correction_log.txt';
        logCorrection($logFile, $oldName, $newName);

        echo json_encode([
            'status' => 'ok',
            'msg' => '✅ 感谢反馈！我们已记录【' . $oldName . '】→【' . $newName . '】的更正建议，核实后会尽快更新。'
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }

    echo json_encode(['error' => '无效的请求'], JSON_UNESCAPED_UNICODE);
    exit;
}

// 其他请求方法
echo json_encode(['error' => '不支持的请求方法'], JSON_UNESCAPED_UNICODE);
