import React, { useState } from "react";
import {
    Modal,
    Stack,
    TextField,
    PrimaryButton,
    DefaultButton,
    MessageBar,
    MessageBarType,
    Spinner,
    SpinnerSize
} from "@fluentui/react";

import styles from "./AddItemModal.module.css";

interface Props {
    isOpen: boolean;
    onClose: () => void;
    onItemCreated: () => void;
}

interface ItemData {
    type: string;
    brand: string;
    name: string;
    description: string;
    price: number;
    owner: string;
}

interface ApiError {
    error: string;
}

export const AddItemModal = ({ isOpen, onClose, onItemCreated }: Props) => {
    const [formData, setFormData] = useState<ItemData>({
        type: "",
        brand: "",
        name: "",
        description: "",
        price: 0,
        owner: ""
    });
    
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    const handleInputChange = (field: keyof ItemData) => (
        event: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>,
        newValue?: string
    ) => {
        const value = newValue !== undefined ? newValue : (event.target as HTMLInputElement).value;
        setFormData(prev => ({
            ...prev,
            [field]: field === 'price' ? parseFloat(value) || 0 : value
        }));
        setError(null);
        setSuccess(false);
    };

    const validateForm = (): boolean => {
        if (!formData.type.trim()) {
            setError("Type is required");
            return false;
        }
        if (!formData.brand.trim()) {
            setError("Brand is required");
            return false;
        }
        if (!formData.name.trim()) {
            setError("Name is required");
            return false;
        }
        if (!formData.description.trim()) {
            setError("Description is required");
            return false;
        }
        if (formData.price <= 0) {
            setError("Price must be greater than 0");
            return false;
        }
        if (!formData.owner.trim()) {
            setError("Owner is required");
            return false;
        }
        return true;
    };

    const handleSubmit = async () => {
        if (!validateForm()) return;

        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch('/items', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                let errorMessage = `HTTP error! status: ${response.status}`;
                try {
                    const errorData: ApiError = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch (parseError) {
                    // If response is not JSON (e.g., HTML error page), use the text content
                    try {
                        const errorText = await response.text();
                        if (errorText.includes('Internal Server Error')) {
                            errorMessage = 'Internal server error occurred. Please try again.';
                        } else {
                            errorMessage = `Server error: ${response.status}`;
                        }
                    } catch (textError) {
                        // Fallback to generic error message
                        errorMessage = `Server error: ${response.status}`;
                    }
                }
                throw new Error(errorMessage);
            }

            setSuccess(true);
            setFormData({
                type: "",
                brand: "",
                name: "",
                description: "",
                price: 0,
                owner: ""
            });
            
            // Wait a moment to show success message, then close and notify parent
            setTimeout(() => {
                setSuccess(false);
                onClose();
                onItemCreated();
            }, 1000);

        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred while creating the item');
        } finally {
            setIsLoading(false);
        }
    };

    const handleClose = () => {
        if (!isLoading) {
            setFormData({
                type: "",
                brand: "",
                name: "",
                description: "",
                price: 0,
                owner: ""
            });
            setError(null);
            setSuccess(false);
            onClose();
        }
    };

    return (
        <Modal
            isOpen={isOpen}
            onDismiss={handleClose}
            isBlocking={isLoading}
            containerClassName={styles.modalContainer}
        >
            <div className={styles.modalContent}>
                <Stack tokens={{ childrenGap: 20 }}>
                    <div className={styles.modalHeader}>
                        <h2>Add New Item</h2>
                    </div>

                    {error && (
                        <MessageBar messageBarType={MessageBarType.error} isMultiline>
                            {error}
                        </MessageBar>
                    )}

                    {success && (
                        <MessageBar messageBarType={MessageBarType.success}>
                            Item created successfully!
                        </MessageBar>
                    )}

                    <Stack tokens={{ childrenGap: 15 }}>
                        <TextField
                            label="Type"
                            placeholder="e.g., Footwear, Jackets, Climbing..."
                            value={formData.type}
                            onChange={handleInputChange('type')}
                            disabled={isLoading}
                            required
                        />

                        <TextField
                            label="Brand"
                            placeholder="e.g., WildRunner, Gravitator..."
                            value={formData.brand}
                            onChange={handleInputChange('brand')}
                            disabled={isLoading}
                            required
                        />

                        <TextField
                            label="Name"
                            placeholder="Product name"
                            value={formData.name}
                            onChange={handleInputChange('name')}
                            disabled={isLoading}
                            required
                        />

                        <TextField
                            label="Description"
                            placeholder="Product description"
                            value={formData.description}
                            onChange={handleInputChange('description')}
                            disabled={isLoading}
                            multiline
                            rows={4}
                            required
                        />

                        <TextField
                            label="Price"
                            placeholder="0.00"
                            value={formData.price.toString()}
                            onChange={handleInputChange('price')}
                            disabled={isLoading}
                            type="number"
                            min="0"
                            step="0.01"
                            required
                        />

                        <TextField
                            label="Owner"
                            placeholder="e.g., John Doe, Company Name..."
                            value={formData.owner}
                            onChange={handleInputChange('owner')}
                            disabled={isLoading}
                            required
                        />
                    </Stack>

                    <Stack horizontal tokens={{ childrenGap: 10 }} className={styles.modalActions}>
                        <PrimaryButton
                            text={isLoading ? "Creating..." : "Create Item"}
                            onClick={handleSubmit}
                            disabled={isLoading}
                        />
                        {isLoading && <Spinner size={SpinnerSize.small} />}
                        <DefaultButton
                            text="Cancel"
                            onClick={handleClose}
                            disabled={isLoading}
                        />
                    </Stack>
                </Stack>
            </div>
        </Modal>
    );
};