# 局域网网盘系统 - 版本信息

## 当前版本
- **版本号**: V1.5_26/03/20
- **发布日期**: 2026年3月20日
- **版本代号**: RAW Preview Edition

## 版本特性
- ✅ RAW格式照片预览支持
- ✅ 增强的文件预览功能
- ✅ 前端用户体验优化
- ✅ 多个问题修复

## 系统要求
- Python 3.8+
- Django 4.2+
- 内存: 至少2GB（用于RAW文件处理）
- 存储: 根据需求配置

## 安装说明
1. 安装依赖: `pip install -r requirements.txt`
2. 数据库迁移: `python manage.py migrate`
3. 创建管理员: `python manage.py createsuperuser`
4. 启动服务器: `python manage.py runserver 0.0.0.0:8000`

## 文件结构
```
V1.5_26/03/20/
├── readme_v1.5.md          # 详细更新日志
├── README.md              # 主说明文档
├── requirements.txt       # 依赖列表
├── .gitignore            # Git忽略文件
└── VERSION.md            # 本文件
```

## 更新内容
详细更新内容请查看 [readme_v1.5.md](readme_v1.5.md)

## 技术支持
- GitHub: [项目地址]
- 文档: 查看项目README.md
- 问题反馈: GitHub Issues

---
**V1.5版本标志着网盘系统在专业文件支持方面的重要进步，为用户提供了更完整、更强大的文件管理体验。**