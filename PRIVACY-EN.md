# MikRapor — Privacy Policy

**Last updated:** 4 August 2026

## Summary

MikRapor is a desktop application that runs on your own computer. Your financial data is
read from your own Mikro ERP system and stays on your machine. MikRapor has no server of
its own; we do not collect, store, or see your data.

The only point at which data leaves your computer is the "AI Commentary" feature, which
you start explicitly.

## 1. Data we collect

None. MikRapor:

- does not require an account and keeps no records;
- sends no usage statistics, telemetry, crash reports, or analytics;
- contains no advertising networks or trackers.

## 2. What is stored on your computer

Your settings are kept only in your own user folder:
`%APPDATA%\MikRapor\config.json`

It contains your Mikro server address, company code, user code, report preferences, and —
if you have entered one — your AI provider API key.

Your Mikro password and API key are never written in plain text; they are protected with
Windows DPAPI encryption and can only be decrypted by the same Windows user. You may delete
this file at any time, and the application will ask for the details again.

The PDF and CSV reports you generate are written only to the folder you choose.

## 3. Your financial data

MikRapor connects to the Mikro ERP system on your own network and computes the report on
your computer. This data is never transmitted to us or to any third party.

## 4. AI Commentary — the only outbound path

This tab sends the report content for the period you selected to an AI provider and asks
for commentary. **No network call is made unless both conditions are met:**

1. you have entered your own API key, and
2. you have ticked the consent checkbox on screen.

**What is sent:** the report content you see on screen — amounts, ratios, and customer /
supplier names included. Nothing that is not on screen is sent.

**Where it goes:** to the provider you select — Anthropic, OpenAI, Google, DeepSeek, xAI,
or a custom endpoint you enter. The request goes directly from your computer to that
provider; there is no MikRapor server in between. How the provider handles the data is
governed by that provider's own privacy policy, and because the key is yours, the terms of
your own account apply.

Clearing the consent checkbox or deleting the key closes this path completely; the rest of
the application is unaffected.

## 5. Licence verification

Whether you own the premium add-on is determined by querying the Microsoft Store service
built into Windows. This query contains none of your financial data; only licence
information is read. Your Microsoft account and purchases are governed by Microsoft's
privacy terms.

## 6. Personal data

Records in your Mikro database may contain personal data (for example, sole traders). The
data controller for that data is your own company, which owns the database. Because
MikRapor never transfers this data to us, we are not a data processor. The only exception
is the transfer described in section 4, which you initiate yourself, and where the
recipient is the AI provider you have contracted with directly.

## 7. Children

MikRapor is a business reporting tool. It is not directed at children and collects no age
information.

## 8. Changes

If this policy changes, the current text will be published on the application's Microsoft
Store page and the date above will be updated.

## 9. Contact

Hidroteknik
Email: mikrapor@hidroteknik.com.tr
