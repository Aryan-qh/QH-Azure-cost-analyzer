# 🔄 Update Summary for Azure Cost Analyzer

This document outlines the latest updates made to the Azure Cost Analyzer project. 


## ✅ **What’s Changed**

### **1. Resource Type → Service Name**

* The cost extraction logic has been updated to use **Azure Service Name** instead of **Resource Type**.

### **2. Enhanced Anomaly Detector**

* The anomaly detection module now:

  * Fetches **all Azure resources** instead of limited subsets
  * Uses a **rolling calendar window** for analysis

### **3. Virtual Network & Bandwidth Added to Cost Report**
