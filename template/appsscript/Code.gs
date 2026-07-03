// Global Variables
var SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE"; // The Google Sheet containing the source data
var FOLDER_NAME = "my_sync_folder"; // Target folder in Google Drive for desktop sync

/**
 * Handle incoming API calls from local Python script.
 * e.g., ?action=export or ?action=import
 */
function doGet(e) {
  if (e && e.parameter && e.parameter.action) {
    var action = e.parameter.action;
    
    if (action === 'export') {
      try {
        exportSheetToExcel();
        return ContentService.createTextOutput(JSON.stringify({success: true, message: "Exported successfully"}))
                             .setMimeType(ContentService.MimeType.JSON);
      } catch (err) {
        return ContentService.createTextOutput(JSON.stringify({success: false, error: err.toString()}))
                             .setMimeType(ContentService.MimeType.JSON);
      }
    }
    
    if (action === 'import') {
      try {
        importExcelToSheet();
        return ContentService.createTextOutput(JSON.stringify({success: true, message: "Imported successfully"}))
                             .setMimeType(ContentService.MimeType.JSON);
      } catch (err) {
        return ContentService.createTextOutput(JSON.stringify({success: false, error: err.toString()}))
                             .setMimeType(ContentService.MimeType.JSON);
      }
    }
  }
  
  // Serve the dashboard HTML UI if no action query parameter is specified
  try {
    return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle('Cloud Data Dashboard')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
      .addMetaTag('viewport', 'width=device-width, initial-scale=1');
  } catch (err) {
    return HtmlService.createHtmlOutput("<h1>Error serving template</h1><pre>" + err.toString() + "</pre>");
  }
}

/**
 * Helper to fetch or create the Google Drive sync folder.
 */
function getTargetFolder() {
  var folders = DriveApp.getFoldersByName(FOLDER_NAME);
  if (folders.hasNext()) {
    return folders.next();
  }
  return DriveApp.createFolder(FOLDER_NAME);
}

/**
 * Exports the target Google Sheet to an Excel file (.xlsx) in Google Drive.
 */
function exportSheetToExcel() {
  var url = "https://docs.google.com/spreadsheets/d/" + SPREADSHEET_ID + "/export?format=xlsx";
  
  var response = UrlFetchApp.fetch(url, {
    headers: {
      'Authorization': 'Bearer ' +  ScriptApp.getOAuthToken(),
    },
    muteHttpExceptions: true
  });
  
  if (response.getResponseCode() === 200) {
    var blob = response.getBlob();
    var fileName = "Cloud_Data.xlsx";
    blob.setName(fileName);
    
    var folder = getTargetFolder();
    
    // Trash existing files with the same name to prevent duplication
    var existingFiles = folder.getFilesByName(fileName);
    while (existingFiles.hasNext()) {
      existingFiles.next().setTrashed(true);
    }
    
    folder.createFile(blob);
    Logger.log("Exported Cloud_Data.xlsx successfully.");
  } else {
    throw new Error("Export failed. Status: " + response.getResponseCode());
  }
}

/**
 * Imports the processed Excel file back from Google Drive into a tab in Google Sheet.
 */
function importExcelToSheet() {
  var folder = getTargetFolder();
  var fileName = "processed_summary.xlsx";
  var files = folder.getFilesByName(fileName);
  
  if (!files.hasNext()) {
    throw new Error("Import file '" + fileName + "' not found in Drive folder.");
  }
  
  var file = files.next();
  var blob = file.getBlob();
  
  // Create a temporary Google Sheet in Drive to convert the Excel file on the fly
  var tempFileMetadata = {
    title: "Temp_Import",
    mimeType: MimeType.GOOGLE_SHEETS
  };
  
  var tempFile = Drive.Files.insert(tempFileMetadata, blob);
  var tempSs = SpreadsheetApp.openById(tempFile.id);
  var tempSheet = tempSs.getSheets()[0];
  var tempValues = tempSheet.getDataRange().getValues();
  
  // Write values to the target Google Sheet
  var mainSs = SpreadsheetApp.openById(SPREADSHEET_ID);
  var targetSheet = mainSs.getSheetByName("SUMMARY") || mainSs.insertSheet("SUMMARY");
  
  targetSheet.clearContents();
  if (tempValues.length > 0) {
    targetSheet.getRange(1, 1, tempValues.length, tempValues[0].length).setValues(tempValues);
  }
  
  // Clean up temporary spreadsheet file
  Drive.Files.remove(tempFile.id);
  Logger.log("Imported data into SUMMARY sheet successfully.");
}
