// ⚙️ 获取服务器状态信息
async function getServerStatus() {
    try {
        const response = await fetch('/status');
        const data = await response.json();
        
        // 更新UI显示服务器状态
        const statusElement = document.getElementById('serverStatus');
        if (statusElement) {
            if (data.translation_running) {
                statusElement.innerHTML = '🟢 翻译服务运行中';
                statusElement.classList.add('running');
                statusElement.classList.remove('stopped');
            } else {
                statusElement.innerHTML = '🔴 翻译服务已停止';
                statusElement.classList.add('stopped');
                statusElement.classList.remove('running');
            }
        }
        
        // 更新房间信息
        const roomsElement = document.getElementById('roomInfo');
        if (roomsElement && data.rooms) {
            roomsElement.innerHTML = `
                <div>中文原音房间: ${data.rooms.chinese}</div>
                <div>韩文翻译房间: ${data.rooms.korean}</div>
                <div>越南文翻译房间: ${data.rooms.vietnamese}</div>
            `;
        }
        
        return data;
    } catch (error) {
        console.error('获取服务器状态失败:', error);
        return null;
    }
}

// 页面加载后自动获取服务器状态
document.addEventListener('DOMContentLoaded', () => {
    // 初始获取状态
    getServerStatus();
    
    // 每30秒更新一次状态
    setInterval(getServerStatus, 30000);
    
    // 添加健康检查按钮事件
    const healthCheckBtn = document.getElementById('healthCheckBtn');
    if (healthCheckBtn) {
        healthCheckBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                
                alert(`服务健康状态: ${data.status === 'ok' ? '正常' : '异常'}`);
            } catch (error) {
                alert('健康检查失败: ' + error.message);
            }
        });
    }
}); 