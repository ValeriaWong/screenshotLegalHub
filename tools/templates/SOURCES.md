# 微信截图样式来源

样式版本：`wechat-github-reference-20261106`。

视觉参考为 [gaopengbin/wechat-dialog-generator](https://github.com/gaopengbin/wechat-dialog-generator)，读取的提交是 `0e64ddb3b1a6843cc92218270bb539a0b2a6b352`：

- [PhonePreview.css](https://github.com/gaopengbin/wechat-dialog-generator/blob/0e64ddb3b1a6843cc92218270bb539a0b2a6b352/src/components/PhonePreview.css)：居中导航、灰底、头像与气泡比例、时间标签、输入栏及橙色转账卡片。文件 Git blob 为 `b14f4fa4d815b0e4441eb5c4268a9c973b658ab6`。
- [PhonePreview.tsx](https://github.com/gaopengbin/wechat-dialog-generator/blob/0e64ddb3b1a6843cc92218270bb539a0b2a6b352/src/components/PhonePreview.tsx)：左右消息、群聊昵称与卡片的布局参考。
- [WechatPhoneHeader.tsx](https://github.com/gaopengbin/wechat-dialog-generator/blob/0e64ddb3b1a6843cc92218270bb539a0b2a6b352/src/components/WechatPhoneHeader.tsx)：状态栏及聊天标题栏参考。

上游 README 声明 MIT，但本次读取的提交中未找到 LICENSE 文件。因此这里只按公开界面结构和比例改写本地样式，未直接打包上游源码、位图、字体、账户或支付功能。`wechat.css` 和本地 SVG 图标、风景头像均在本项目实现；没有使用真实当事人头像。头像与状态栏仅为固定的样式装饰，不是来源证据。

原模板保留给 WhatsApp 和中性通信摘录；新样式仅作用于 `.phone.wechat`。输出保持 430×932 CSS 像素、2 倍截图。金额、消息内容、收款状态及日期精度仍取自既有数据；未知收款状态不会绘制成“已接收”。图中保留“合成研究样本”标记。

将当前渲染器纳入新的冻结快照时，须同时纳入 `tools/templates/wechat.css` 和本文件。已有 V3 冻结快照不改写。
