const STYLE_ATOMS = {
  "text-xs":{fontSize:"11px"},"text-sm":{fontSize:"13px"},"text-base":{fontSize:"14px"},"text-lg":{fontSize:"16px"},"text-xl":{fontSize:"18px"},
  "font-light":{fontWeight:"300"},"font-normal":{fontWeight:"400"},"font-medium":{fontWeight:"500"},"font-semibold":{fontWeight:"600"},"font-bold":{fontWeight:"700"},
  "font-sans":{fontFamily:"'DM Sans','Noto Sans SC',system-ui,sans-serif"},"font-mono":{fontFamily:"'Source Code Pro','Fira Code',ui-monospace,monospace"},"font-serif":{fontFamily:"'Lora','Noto Serif SC',serif"},
  "color-primary":{color:"#1a1a1a"},"color-secondary":{color:"#555"},"color-muted":{color:"#888"},"color-accent":{color:"#2563eb"},"color-success":{color:"#16a34a"},"color-warning":{color:"#b45309"},"color-danger":{color:"#dc2626"},"color-white":{color:"#fff"},
  "color-term-green":{color:"#4ade80"},"color-term-gray":{color:"#d1d5db"},"color-term-red":{color:"#f87171"},
  "bg-none":{backgroundColor:"transparent"},"bg-white":{backgroundColor:"#fff"},"bg-gray-50":{backgroundColor:"#f8f9fa"},"bg-gray-100":{backgroundColor:"#f1f3f5"},"bg-gray-900":{backgroundColor:"#1a1a2e"},
  "bg-blue-50":{backgroundColor:"#eff6ff"},"bg-green-50":{backgroundColor:"#f0fdf4"},"bg-amber-50":{backgroundColor:"#fffbeb"},"bg-red-50":{backgroundColor:"#fef2f2"},"bg-purple-50":{backgroundColor:"#faf5ff"},
  "p-0":{padding:"0"},"p-2":{padding:"8px"},"p-3":{padding:"12px"},"p-4":{padding:"16px"},"p-5":{padding:"20px"},
  "rounded-none":{borderRadius:"0"},"rounded-sm":{borderRadius:"4px"},"rounded-md":{borderRadius:"8px"},"rounded-lg":{borderRadius:"12px"},
  "border":{border:"1px solid #e5e7eb"},"border-l-blue":{borderLeft:"3px solid #3b82f6"},"border-l-green":{borderLeft:"3px solid #22c55e"},"border-l-amber":{borderLeft:"3px solid #f59e0b"},"border-l-red":{borderLeft:"3px solid #ef4444"},"border-l-purple":{borderLeft:"3px solid #a855f7"},"border-l-gray":{borderLeft:"3px solid #d1d5db"},
  "leading-tight":{lineHeight:"1.4"},"leading-normal":{lineHeight:"1.6"},"leading-relaxed":{lineHeight:"1.75"},
  "italic":{fontStyle:"italic"},"not-italic":{fontStyle:"normal"},
  "shadow-sm":{boxShadow:"0 1px 2px rgba(0,0,0,0.04)"},"shadow":{boxShadow:"0 1px 3px rgba(0,0,0,0.08)"}
};
const STYLE_PRESETS = {
  "默认正文":{desc:"标准正文",atoms:["text-base","font-sans","color-primary","bg-none","leading-relaxed"]},
  "淡蓝信息":{desc:"蓝底蓝线",atoms:["text-sm","font-sans","color-accent","bg-blue-50","border-l-blue","p-4","rounded-md","leading-normal"]},
  "灰底代码":{desc:"浅灰代码块",atoms:["text-sm","font-mono","color-primary","bg-gray-100","p-4","rounded-lg","leading-tight","border"]},
  "暗色终端":{desc:"深色终端",atoms:["text-sm","font-mono","color-term-green","bg-gray-900","p-4","rounded-lg","leading-tight"]},
  "终端输出":{desc:"终端stdout",atoms:["text-sm","font-mono","color-term-gray","bg-gray-900","p-4","rounded-lg","leading-tight"]},
  "终端错误":{desc:"终端stderr",atoms:["text-sm","font-mono","color-term-red","bg-gray-900","p-4","rounded-lg","leading-tight"]},
  "思考链":{desc:"灰色斜体",atoms:["text-sm","font-sans","color-muted","bg-gray-50","border-l-gray","p-4","rounded-md","italic","leading-normal"]},
  "成功":{desc:"绿底绿线",atoms:["text-sm","font-sans","color-success","bg-green-50","border-l-green","p-4","rounded-md","leading-normal"]},
  "警告":{desc:"黄底黄线",atoms:["text-sm","font-sans","color-warning","bg-amber-50","border-l-amber","p-4","rounded-md","leading-normal"]},
  "错误":{desc:"红底红线",atoms:["text-sm","font-sans","color-danger","bg-red-50","border-l-red","p-4","rounded-md","leading-normal"]},
  "工具调用":{desc:"紫底紫线",atoms:["text-sm","font-mono","color-primary","bg-purple-50","border-l-purple","p-4","rounded-md","leading-tight"]},
  "无样式":{desc:"清除样式",atoms:[]}
};
const RENDERER_CONFIG = {
  _default:{label:"默认",component:"markdown",layout:"inline",preset:"默认正文",atoms:["text-base","font-sans","color-primary","bg-none","leading-relaxed"],style:{}},
  text:{label:"正文",component:"markdown",layout:"inline",preset:"默认正文",atoms:["text-base","font-sans","color-primary","bg-none","leading-relaxed"],style:{}},
  thinking:{label:"思考",component:"text",layout:"inline",icon:"",collapsible:true,defaultCollapsed:false,preset:"思考链",atoms:["text-sm","font-sans","color-muted","bg-gray-50","border-l-gray","p-4","rounded-md","italic","leading-normal"],style:{}},
  reasoning:{label:"推理",component:"text",layout:"inline",icon:"",collapsible:true,defaultCollapsed:false,preset:"思考链",atoms:["text-sm","font-sans","color-muted","bg-gray-50","border-l-gray","p-4","rounded-md","italic","leading-normal"],style:{}},
  code:{label:"代码",component:"code",layout:"inline",preset:"灰底代码",atoms:["text-sm","font-mono","color-primary","bg-gray-100","p-4","rounded-lg","leading-tight","border"],style:{}},
  bash:{label:"命令",component:"terminal",layout:"panel",icon:"",preset:"暗色终端",atoms:["text-sm","font-mono","color-term-green","bg-gray-900","p-4","rounded-lg","leading-tight"],style:{}},
  stdout:{label:"输出",component:"terminal",layout:"panel",icon:"",preset:"终端输出",atoms:["text-sm","font-mono","color-term-gray","bg-gray-900","p-4","rounded-lg","leading-tight"],style:{}},
  stderr:{label:"错误输出",component:"terminal",layout:"panel",icon:"",preset:"终端错误",atoms:["text-sm","font-mono","color-term-red","bg-gray-900","p-4","rounded-lg","leading-tight"],style:{}},
  json:{label:"JSON",component:"json",layout:"inline",icon:"{ }",collapsible:true,preset:"灰底代码",atoms:["text-sm","font-mono","color-primary","bg-gray-100","p-4","rounded-lg","leading-tight","border"],style:{}},
  table:{label:"表格",component:"table",layout:"inline",atoms:["text-sm","font-sans","color-primary"],style:{}},
  html:{label:"HTML",component:"html",layout:"inline",maxHeight:"500px",atoms:[],style:{}},
  image:{label:"图片",component:"image",layout:"inline",atoms:["rounded-lg"],style:{maxWidth:"100%"}},
  file:{label:"文件",component:"file",layout:"inline",icon:"",atoms:["text-sm","font-sans","color-primary","bg-gray-50","p-3","rounded-md","border"],style:{},filePreview:{kind:"auto",source:"auto",mode:"drawer",title:"文件预览"}},
  file_excel_base64:{label:"Excel(Base64)",component:"file",layout:"inline",icon:"",atoms:["text-sm","font-sans","color-primary","bg-gray-50","p-3","rounded-md","border"],style:{},filePreview:{kind:"excel",source:"base64",mode:"drawer",title:"Excel 预览"}},
  file_excel_url:{label:"Excel(URL)",component:"file",layout:"inline",icon:"",atoms:["text-sm","font-sans","color-primary","bg-gray-50","p-3","rounded-md","border"],style:{},filePreview:{kind:"excel",source:"url",mode:"drawer",title:"Excel 预览"}},
  tool_call:{label:"工具调用",component:"code",layout:"inline",icon:"",collapsible:true,defaultCollapsed:true,preset:"工具调用",atoms:["text-sm","font-mono","color-primary","bg-purple-50","border-l-purple","p-4","rounded-md","leading-tight"],style:{},transform:{enabled:false,bufferUntil:"json",expression:"return data.result || JSON.stringify(data, null, 2)",placeholder:"处理中..."}},
  tool_result:{label:"工具结果",component:"code",layout:"inline",icon:"",collapsible:true,defaultCollapsed:true,preset:"成功",atoms:["text-sm","font-mono","color-primary","bg-green-50","border-l-green","p-4","rounded-md","leading-tight"],style:{}},
  status:{label:"状态",component:"text",layout:"inline",icon:"",preset:"淡蓝信息",atoms:["text-sm","font-sans","color-accent","bg-blue-50","border-l-blue","p-4","rounded-md","leading-normal"],style:{}},
  error:{label:"错误",component:"text",layout:"inline",icon:"",preset:"错误",atoms:["text-sm","font-sans","color-danger","bg-red-50","border-l-red","p-4","rounded-md","leading-normal"],style:{}},
  warning:{label:"警告",component:"text",layout:"inline",icon:"",preset:"警告",atoms:["text-sm","font-sans","color-warning","bg-amber-50","border-l-amber","p-4","rounded-md","leading-normal"],style:{}}
};
function resolveAtoms(n){var r={};if(!Array.isArray(n))return r;n.forEach(function(k){if(STYLE_ATOMS[k])Object.assign(r,STYLE_ATOMS[k])});return r}
function resolveStyle(c){return Object.assign(resolveAtoms(c.atoms||[]),c.style||{})}
window.RENDERER_CONFIG=RENDERER_CONFIG;window.STYLE_ATOMS=STYLE_ATOMS;window.STYLE_PRESETS=STYLE_PRESETS;window.resolveAtoms=resolveAtoms;window.resolveStyle=resolveStyle;
