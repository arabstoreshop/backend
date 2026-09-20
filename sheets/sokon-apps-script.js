 /**
 * Sukoon + Naseem orders → ONE Google Sheet, TWO tabs
 *
 * Tab «الطلبات»     = سُكون
 * Tab «nassim order» = naseem.beauty
 *
 * 1. Extensions → Apps Script → replace ALL code with this file
 * 2. Save (Ctrl/Cmd+S)
 * 3. Select createNassimOrderTab → Run (once) — Allow → creates the tab
 * 4. Deploy → Manage deployments → pencil → Version: New version → Deploy
 */

var NASEEM_TAB = "nassim order";

var SUKOON_HEADERS = [
  "رقم الطلب",
  "الاسم",
  "الجوال",
  "المدينة",
  "الباقة",
  "السعر",
  "التاريخ",
  "المصدر"
];

var NASEEM_HEADERS = [
  "رقم الطلب",
  "الاسم",
  "الجوال",
  "المدينة",
  "العنوان",
  "المنتجات",
  "المبلغ",
  "الحالة",
  "التاريخ",
  "ملاحظات"
];

var NOTIFY_EMAIL = "";

function createNassimOrderTab() {
  formatSheet();
}

function doGet(e) {
  return saveOrder_(e);
}

function doPost(e) {
  return saveOrder_(e);
}

function saveOrder_(e) {
  var p = readParams_(e);
  var name = String(p.name || "").trim();
  var phone = String(p.phone || p.phone_e164 || "").trim();
  var orderNumber = String(p.order_number || "").trim();
  if (!name && !phone && !orderNumber) {
    return json_({ ok: true, skipped: true });
  }

  if (isNaseem_(p, orderNumber)) {
    return saveNaseem_(p, name, phone, orderNumber);
  }
  return saveSukoon_(p, name, phone);
}

function isNaseem_(p, orderNumber) {
  var brand = String(p.brand || p.source || "").toLowerCase();
  if (brand.indexOf("naseem") !== -1 || brand.indexOf("نسيم") !== -1) return true;
  if (orderNumber.indexOf("NSM-") === 0) return true;
  return false;
}

function saveSukoon_(p, name, phone) {
  var sheet = sukoonSheet_();
  ensureSukoonLayout_(sheet);
  var row = sheet.getLastRow() + 1;
  var orderId = nextSukoonId_(sheet);
  sheet.getRange(row, 1, 1, 8).setValues([[
    orderId,
    name,
    phone,
    String(p.city || "").trim(),
    String(p.pack_title || p.pack || "").trim(),
    p.price || "",
    new Date(),
    String(p.source || "").trim() || "مباشر"
  ]]);
  sheet.getRange(row, 3).setNumberFormat("@");
  sheet.getRange(row, 6).setNumberFormat("#,##0");
  sheet.getRange(row, 7).setNumberFormat("yyyy-mm-dd hh:mm");
  try {
    notifyEmail_({
      brand: "سُكون",
      orderId: orderId,
      name: name,
      phone: phone,
      city: String(p.city || "").trim(),
      extra: "الباقة: " + String(p.pack_title || p.pack || "").trim(),
      price: p.price || "",
      source: String(p.source || "").trim() || "مباشر"
    });
  } catch (err) {}
  return json_({ ok: true, order_id: orderId, tab: "الطلبات" });
}

function saveNaseem_(p, name, phone, orderNumber) {
  var sheet = naseemSheet_();
  ensureNaseemLayout_(sheet);
  var products = naseemProducts_(p);
  var row = sheet.getLastRow() + 1;
  var orderId = orderNumber || nextNaseemId_(sheet);
  sheet.getRange(row, 1, 1, 10).setValues([[
    orderId,
    name,
    phone,
    String(p.city || "").trim(),
    String(p.address || "").trim(),
    products,
    p.total_sar || p.price || "",
    String(p.status || "pending").trim() || "pending",
    new Date(),
    String(p.notes || "").trim()
  ]]);
  sheet.getRange(row, 3).setNumberFormat("@");
  sheet.getRange(row, 7).setNumberFormat("#,##0");
  sheet.getRange(row, 9).setNumberFormat("yyyy-mm-dd hh:mm");
  try {
    notifyEmail_({
      brand: "نسيم",
      orderId: orderId,
      name: name,
      phone: phone,
      city: String(p.city || "").trim(),
      extra: "المنتجات: " + products,
      price: p.total_sar || p.price || "",
      source: "naseem.beauty"
    });
  } catch (err) {}
  return json_({ ok: true, order_id: orderId, tab: NASEEM_TAB });
}

function naseemProducts_(p) {
  if (p.products) return String(p.products);
  var items = p.items;
  if (typeof items === "string") {
    try { items = JSON.parse(items); } catch (err) { items = []; }
  }
  if (!items || !items.length) return String(p.pack_title || p.pack || "");
  return items.map(function (i) {
    return String(i.product_name || i.sku || "") + " x" + String(i.quantity || 1);
  }).join(" | ");
}

function sukoonSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName("الطلبات") || ss.getSheets()[0];
}

function naseemSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(NASEEM_TAB) || ss.getSheetByName("نسيم");
  if (sheet) {
    if (sheet.getName() !== NASEEM_TAB) sheet.setName(NASEEM_TAB);
    return sheet;
  }
  sheet = ss.insertSheet(NASEEM_TAB);
  ensureNaseemLayout_(sheet);
  return sheet;
}

function notifyAddress_() {
  if (NOTIFY_EMAIL) return NOTIFY_EMAIL;
  try {
    var owner = SpreadsheetApp.getActiveSpreadsheet().getOwner();
    if (owner && owner.getEmail()) return owner.getEmail();
  } catch (err) {}
  try {
    return Session.getEffectiveUser().getEmail() || "";
  } catch (err2) {
    return "";
  }
}

function notifyEmail_(o) {
  var to = notifyAddress_();
  if (!to) return;
  MailApp.sendEmail({
    to: to,
    subject: "طلب " + o.brand + " " + o.orderId + " — " + o.phone,
    body: [
      "طلب " + o.brand + " جديد " + o.orderId,
      "الاسم: " + o.name,
      "الجوال: " + o.phone,
      "المدينة: " + o.city,
      o.extra,
      "المبلغ: " + o.price,
      "المصدر: " + o.source
    ].join("\n")
  });
}

function formatSheet() {
  ensureSukoonLayout_(sukoonSheet_());
  cleanupEmpty_(sukoonSheet_(), 2, 3);
  ensureNaseemLayout_(naseemSheet_());
  cleanupEmpty_(naseemSheet_(), 2, 3);
}

function ensureSukoonLayout_(sheet) {
  sheet.setRightToLeft(true);
  if (sheet.getName() !== NASEEM_TAB && sheet.getName() !== "نسيم") sheet.setName("الطلبات");
  var a1 = String(sheet.getRange(1, 1).getValue() || "");
  if (a1 !== SUKOON_HEADERS[0]) {
    sheet.insertRowBefore(1);
    sheet.getRange(1, 1, 1, SUKOON_HEADERS.length).setValues([SUKOON_HEADERS]);
  } else if (String(sheet.getRange(1, 8).getValue() || "") !== SUKOON_HEADERS[7]) {
    sheet.getRange(1, 8).setValue(SUKOON_HEADERS[7]);
  }
  styleHeader_(sheet, SUKOON_HEADERS.length, "#e2c08a", "#070b12");
  sheet.setColumnWidth(1, 110);
  sheet.setColumnWidth(2, 140);
  sheet.setColumnWidth(3, 130);
  sheet.setColumnWidth(4, 110);
  sheet.setColumnWidth(5, 180);
  sheet.setColumnWidth(6, 80);
  sheet.setColumnWidth(7, 150);
  sheet.setColumnWidth(8, 110);
}

function ensureNaseemLayout_(sheet) {
  sheet.setRightToLeft(true);
  sheet.setName(NASEEM_TAB);
  var a1 = String(sheet.getRange(1, 1).getValue() || "");
  if (a1 !== NASEEM_HEADERS[0] || String(sheet.getRange(1, 6).getValue() || "") !== NASEEM_HEADERS[5]) {
    if (sheet.getLastRow() === 0) {
      sheet.getRange(1, 1, 1, NASEEM_HEADERS.length).setValues([NASEEM_HEADERS]);
    } else if (a1 !== NASEEM_HEADERS[0]) {
      sheet.insertRowBefore(1);
      sheet.getRange(1, 1, 1, NASEEM_HEADERS.length).setValues([NASEEM_HEADERS]);
    } else {
      sheet.getRange(1, 1, 1, NASEEM_HEADERS.length).setValues([NASEEM_HEADERS]);
    }
  }
  styleHeader_(sheet, NASEEM_HEADERS.length, "#1b5e4a", "#ffffff");
  sheet.setColumnWidth(1, 160);
  sheet.setColumnWidth(2, 140);
  sheet.setColumnWidth(3, 130);
  sheet.setColumnWidth(4, 110);
  sheet.setColumnWidth(5, 180);
  sheet.setColumnWidth(6, 280);
  sheet.setColumnWidth(7, 90);
  sheet.setColumnWidth(8, 90);
  sheet.setColumnWidth(9, 150);
  sheet.setColumnWidth(10, 160);
}

function styleHeader_(sheet, cols, bg, fg) {
  var header = sheet.getRange(1, 1, 1, cols);
  header.setFontWeight("bold")
    .setBackground(bg)
    .setFontColor(fg)
    .setHorizontalAlignment("center");
  sheet.setFrozenRows(1);
  if (!sheet.getFilter()) {
    sheet.getRange(1, 1, Math.max(sheet.getLastRow(), 1), cols).createFilter();
  }
}

function cleanupEmpty_(sheet, nameCol, phoneCol) {
  var last = sheet.getLastRow();
  if (last < 2) return;
  for (var r = last; r >= 2; r--) {
    var name = String(sheet.getRange(r, nameCol).getValue() || "").trim();
    var phone = String(sheet.getRange(r, phoneCol).getValue() || "").trim();
    if (!name && !phone) sheet.deleteRow(r);
  }
}

function nextSukoonId_(sheet) {
  var last = sheet.getLastRow();
  var n = 0;
  if (last >= 2) {
    var prev = String(sheet.getRange(last, 1).getValue() || "");
    n = parseInt(prev.replace(/\D/g, ""), 10) || (last - 1);
  }
  return "SK-" + ("0000" + (n + 1)).slice(-4);
}

function nextNaseemId_(sheet) {
  var last = sheet.getLastRow();
  var n = 0;
  if (last >= 2) {
    var prev = String(sheet.getRange(last, 1).getValue() || "");
    n = parseInt(prev.replace(/\D/g, ""), 10) || (last - 1);
  }
  return "NSM-" + ("0000" + (n + 1)).slice(-4);
}

function readParams_(e) {
  var p = {};
  if (e && e.parameter) {
    Object.keys(e.parameter).forEach(function (k) {
      p[k] = e.parameter[k];
    });
  }
  if (e && e.postData && e.postData.contents) {
    var raw = e.postData.contents;
    try {
      var json = JSON.parse(raw);
      Object.keys(json).forEach(function (k) {
        if (json[k] != null && json[k] !== "") p[k] = json[k];
      });
    } catch (err) {
      raw.split("&").forEach(function (pair) {
        var i = pair.indexOf("=");
        if (i < 1) return;
        var k = decodeURIComponent(pair.substring(0, i).replace(/\+/g, " "));
        var v = decodeURIComponent(pair.substring(i + 1).replace(/\+/g, " "));
        if (v) p[k] = v;
      });
    }
  }
  return p;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
