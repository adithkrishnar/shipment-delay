import React from 'react';
import { createPortal } from 'react-dom';

const Modal = ({ isOpen, onClose, title, children }) => {
  if (!isOpen) return null;

  return createPortal(
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(5, 8, 15, 0.75)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }} onClick={onClose}>
      <div style={{
        backgroundColor: '#101a2b',
        border: '1px solid #203049',
        borderRadius: '16px',
        padding: '24px',
        maxWidth: '600px',
        width: '90%',
        maxHeight: '85vh',
        overflowY: 'auto',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.3)'
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ margin: 0, fontSize: '20px', color: '#f5f8fc' }}>{title}</h2>
          <button 
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#8998ad',
              fontSize: '24px',
              cursor: 'pointer',
              lineHeight: 1
            }}
          >&times;</button>
        </div>
        <div style={{ color: '#d9e2ed', fontSize: '14px', lineHeight: '1.6' }}>
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default Modal;
